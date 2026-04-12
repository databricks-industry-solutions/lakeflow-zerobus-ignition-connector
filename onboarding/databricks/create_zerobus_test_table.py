#!/usr/bin/env python3
"""Create agl_demo.ot.zerobus_test and grant SP UC permissions for the Zerobus SDK test.

Run from repo root after db-setup-sql (catalog/schema and SP grants exist). Uses Statement Execution API.
Creates the table then grants MODIFY, SELECT to the service principal so Zerobus OAuth can scope to it.

Usage:
  DATABRICKS_CONFIG_PROFILE=daveok SP_APPLICATION_ID=<sp-client-id> uv run --with databricks-sdk python onboarding/databricks/create_zerobus_test_table.py

Optional env: CATALOG (default agl_demo), SCHEMA (default ot), DATABRICKS_WAREHOUSE_ID (default e4082fdb7ea19a15),
  SP_APPLICATION_ID (service principal client_id for UC grants; required for Zerobus write).
"""

from __future__ import annotations

import os
import sys

from databricks.sdk import WorkspaceClient

DEFAULT_WAREHOUSE_ID = "e4082fdb7ea19a15"
DEFAULT_CATALOG = "agl_demo"
DEFAULT_SCHEMA = "ot"
DEFAULT_SP_APPLICATION_ID = "66c066ad-d5a9-496f-8da5-6d7bc2f5d954"


def execute(w: WorkspaceClient, warehouse_id: str, statement: str, desc: str) -> bool:
    try:
        resp = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=statement.strip(),
            wait_timeout="30s",
        )
        status = getattr(resp, "status", None)
        state = getattr(status, "state", None) if status else None
        ok = state is not None and (state == "SUCCEEDED" or str(state).endswith("SUCCEEDED"))
        if not ok:
            msg = getattr(status, "message", "") if status else ""
            err = getattr(status, "error", None) if status else None
            err_str = getattr(err, "message", "") if err else str(err) if err else ""
            print(f"FAILED {desc}: state={state} message={msg} error={err_str}", file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"FAILED {desc}: {e}", file=sys.stderr)
        return False


def main() -> int:
    profile = os.environ.get("DATABRICKS_CONFIG_PROFILE", "daveok")
    warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", DEFAULT_WAREHOUSE_ID)
    catalog = os.environ.get("CATALOG", DEFAULT_CATALOG)
    schema = os.environ.get("SCHEMA", DEFAULT_SCHEMA)
    sp_id = os.environ.get("SP_APPLICATION_ID", DEFAULT_SP_APPLICATION_ID)
    table = f"{catalog}.{schema}.zerobus_test"

    create_sql = f"""
CREATE TABLE IF NOT EXISTS {table} (
  device_name STRING,
  temp        DOUBLE,
  humidity    DOUBLE
)
"""
    grant_sql = f"GRANT MODIFY, SELECT ON TABLE {table} TO `{sp_id}`"

    print(f"Creating table {table} (profile={profile}, warehouse_id={warehouse_id})...")
    w = WorkspaceClient(profile=profile)
    if not execute(w, warehouse_id, create_sql, "CREATE TABLE"):
        return 1
    print(f"Granting SP {sp_id} MODIFY, SELECT on {table}...")
    if not execute(w, warehouse_id, grant_sql, "GRANT"):
        return 1
    print(f"Table {table} ready; SP has UC write. Run: make zerobus-test (or cd zerobus-test && uv run python test_zerobus.py with .env)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
