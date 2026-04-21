"""Unity Catalog GRANT helpers for service principals (connector SP, app SP).

Can also be run as a CLI to grant UC access to a Databricks App's auto-generated SP:

    python uc_grants.py --app-name zerobus-ignition-agl
"""

from __future__ import annotations

import argparse
import os
import sys

from databricks.sdk import WorkspaceClient


def run_grants(
    w: WorkspaceClient,
    sp_application_id: str,
    catalog: str,
    schema: str,
    warehouse_id: str,
) -> None:
    """Run UC GRANT statements so the principal can use catalog/schema and read/write tables.

    Used for both the Ignition Zerobus connector SP and the Databricks App's SP.
    """
    stmts = [
        f"GRANT USE CATALOG ON CATALOG {catalog} TO `{sp_application_id}`",
        f"GRANT USE SCHEMA ON SCHEMA {catalog}.{schema} TO `{sp_application_id}`",
        f"GRANT MODIFY, SELECT ON SCHEMA {catalog}.{schema} TO `{sp_application_id}`",
        f"GRANT READ VOLUME ON VOLUME {catalog}.{schema}.wheels TO `{sp_application_id}`",
    ]
    print(f"  Running {len(stmts)} GRANT statements...")
    for i, stmt in enumerate(stmts, 1):
        try:
            resp = w.statement_execution.execute_statement(
                warehouse_id=warehouse_id,
                statement=stmt,
                wait_timeout="30s",
            )
            state = ""
            if resp.status:
                state = str(getattr(resp.status, "state", ""))
            if "SUCCEEDED" in state:
                print(f"    [{i}/{len(stmts)}] OK")
            else:
                msg = getattr(resp.status, "message", "") if resp.status else ""
                print(f"    [{i}/{len(stmts)}] WARN: state={state} {msg}")
        except Exception as e:
            print(f"    [{i}/{len(stmts)}] WARN: {e}")


def resolve_app_sp(w: WorkspaceClient, app_name: str) -> str | None:
    """Look up the application_id for a Databricks App's auto-generated SP."""
    try:
        app = w.apps.get(name=app_name)
        if not app or not app.service_principal_id:
            return None
        sp = w.service_principals.get(id=str(app.service_principal_id))
        return sp.application_id or str(app.service_principal_id)
    except Exception:
        return None


def main() -> int:
    p = argparse.ArgumentParser(description="Grant UC privileges to a Databricks App SP")
    p.add_argument("--app-name", default=os.environ.get("APP_NAME", "zerobus-ignition-agl"))
    p.add_argument("--catalog", default=os.environ.get("CATALOG", "agl_demo"))
    p.add_argument("--schema", default=os.environ.get("SCHEMA", "ot"))
    p.add_argument("--warehouse-id", default=os.environ.get("DATABRICKS_WAREHOUSE_ID", "e4082fdb7ea19a15"))
    p.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE", "daveok"))
    args = p.parse_args()

    w = WorkspaceClient(profile=args.profile)
    app_id = resolve_app_sp(w, args.app_name)
    if not app_id:
        print(f"Could not resolve SP for app '{args.app_name}'. Is the app deployed?", file=sys.stderr)
        return 1

    print(f"App '{args.app_name}' SP application_id: {app_id}")
    run_grants(w, app_id, args.catalog, args.schema, args.warehouse_id)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
