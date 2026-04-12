#!/usr/bin/env python3
"""Provision Lakebase for direct DAB deployment and emit connector credentials.

This workflow is idempotent and combines:
1) Lakebase instance resolve/create (Databricks CLI)
2) PostgreSQL object + role setup (psycopg)
3) UC grants for the connector SP (Databricks SDK statement execution)
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient

# Ensure repo root is importable when run from make
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from onboarding.databricks.lakebase_grants import (  # noqa: E402
    apply_sql_file,
    connect_postgres,
    ensure_database,
    ensure_login_role,
    grant_app_query_privileges,
    grant_connector_privileges,
)
from onboarding.databricks.uc_grants import run_grants as run_uc_grants  # noqa: E402

DEFAULT_INSTANCE = "agl-demo-lakebase"
DEFAULT_CAPACITY = "CU_1"
DEFAULT_DB = "databricks_postgres"
DEFAULT_TABLE = "raw_tags"
DEFAULT_SCHEMA = "public"
DEFAULT_CONNECTOR_ROLE = "zerobus_connector"
DEFAULT_ARTIFACT = ".lakebase-connector.env"
DEFAULT_APP_NAME = "zerobus-ignition-agl"


def _run_json(cmd: list[str], env: dict[str, str]) -> dict:
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({' '.join(cmd)}): {proc.stderr.strip() or proc.stdout.strip()}")
    text = proc.stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k, v = stripped.split("=", 1)
        values[k.strip()] = v.strip()
    return values


def _autogenerate_admin_credential(*, profile: str, host: str | None, instance_name: str) -> tuple[str, str]:
    env = os.environ.copy()
    env["DATABRICKS_CONFIG_PROFILE"] = profile
    if host:
        env["DATABRICKS_HOST"] = host

    me = _run_json(["databricks", "current-user", "me", "-o", "json"], env)
    user = me.get("userName")
    if not user:
        emails = me.get("emails") or []
        for e in emails:
            if isinstance(e, dict) and e.get("value"):
                user = e["value"]
                break
    if not user:
        raise RuntimeError("Could not resolve current workspace user for generated Lakebase credential")

    cred_req = json.dumps({"instance_names": [instance_name]})
    cred = _run_json(
        [
            "databricks",
            "database",
            "generate-database-credential",
            "--json",
            cred_req,
            "-o",
            "json",
        ],
        env,
    )
    token = cred.get("token")
    if not token:
        raise RuntimeError("Generated Lakebase credential response did not include a token")

    return user, token


def _resolve_instance_host(instance: dict) -> str | None:
    candidates = [
        instance.get("read_write_dns"),
        instance.get("readWriteDns"),
        instance.get("host"),
        instance.get("endpoint"),
    ]
    for key in ("spec", "status", "database_instance", "databaseInstance"):
        obj = instance.get(key)
        if isinstance(obj, dict):
            candidates.extend(
                [
                    obj.get("read_write_dns"),
                    obj.get("readWriteDns"),
                    obj.get("host"),
                    obj.get("endpoint"),
                ]
            )
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip()
    return None


def _ensure_instance(*, profile: str, host: str | None, instance_name: str, capacity: str) -> dict:
    env = os.environ.copy()
    env["DATABRICKS_CONFIG_PROFILE"] = profile
    if host:
        env["DATABRICKS_HOST"] = host

    get_cmd = ["databricks", "database", "get-database-instance", instance_name, "-o", "json"]

    def _wait_until_resolvable(max_attempts: int = 24, sleep_s: int = 5) -> dict:
        last: dict = {}
        for _ in range(max_attempts):
            last = _run_json(get_cmd, env)
            if last and _resolve_instance_host(last):
                return last
            time.sleep(sleep_s)
        return last

    try:
        instance = _run_json(get_cmd, env)
        if instance:
            print(f"Using existing Lakebase instance: {instance_name}")
            if _resolve_instance_host(instance):
                return instance
            print("Waiting for Lakebase instance endpoint to become available...")
            return _wait_until_resolvable()
    except Exception:
        pass

    print(f"Creating Lakebase instance: {instance_name} (capacity={capacity})")
    create_cmd = [
        "databricks",
        "database",
        "create-database-instance",
        instance_name,
        "--capacity",
        capacity,
        "--enable-pg-native-login",
        "-o",
        "json",
    ]
    _run_json(create_cmd, env)
    print("Waiting for Lakebase instance endpoint to become available...")
    return _wait_until_resolvable()


def _read_profile_client_id(profile_name: str) -> str | None:
    cfg = configparser.ConfigParser()
    cfg.read(Path.home() / ".databrickscfg")
    return cfg.get(profile_name, "client_id", fallback=None)


def _app_service_principal_application_id(w: WorkspaceClient, app_name: str) -> str | None:
    try:
        app = w.apps.get(name=app_name)
        if not app or not app.service_principal_id:
            return None
        sp = w.service_principals.get(id=str(app.service_principal_id))
        return sp.application_id or str(app.service_principal_id)
    except Exception:
        return None


def main() -> int:
    p = argparse.ArgumentParser(description="Provision Lakebase directly for DAB/app/connector usage")
    p.add_argument("--instance-name", default=os.environ.get("LAKEBASE_INSTANCE_NAME", DEFAULT_INSTANCE))
    p.add_argument("--instance-capacity", default=os.environ.get("LAKEBASE_INSTANCE_CAPACITY", DEFAULT_CAPACITY))
    p.add_argument("--database-name", default=os.environ.get("LAKEBASE_DATABASE", DEFAULT_DB))
    p.add_argument("--database-schema", default=os.environ.get("LAKEBASE_SCHEMA", DEFAULT_SCHEMA))
    p.add_argument("--table-name", default=os.environ.get("LAKEBASE_TABLE", DEFAULT_TABLE))
    p.add_argument("--admin-user", default=os.environ.get("LAKEBASE_USER", ""))
    p.add_argument("--admin-password", default=os.environ.get("LAKEBASE_PASSWORD", ""))
    p.add_argument("--admin-port", type=int, default=int(os.environ.get("LAKEBASE_PORT", "5432")))
    p.add_argument("--connector-role-name", default=os.environ.get("CONNECTOR_ROLE_NAME", DEFAULT_CONNECTOR_ROLE))
    p.add_argument("--connector-role-password", default=os.environ.get("CONNECTOR_ROLE_PASSWORD", ""))
    p.add_argument("--connector-sp-profile", default=os.environ.get("SP_PROFILE_NAME", "agl-demo"))
    p.add_argument("--connector-sp-application-id", default=os.environ.get("SP_APPLICATION_ID", ""))
    p.add_argument("--catalog", default=os.environ.get("CATALOG", "agl_demo"))
    p.add_argument("--schema", default=os.environ.get("SCHEMA", "ot"))
    p.add_argument("--warehouse-id", default=os.environ.get("DATABRICKS_WAREHOUSE_ID", ""))
    p.add_argument("--app-name", default=os.environ.get("APP_NAME", DEFAULT_APP_NAME))
    p.add_argument("--artifact-path", default=os.environ.get("LAKEBASE_CONNECTOR_ARTIFACT", DEFAULT_ARTIFACT))
    p.add_argument("--databricks-profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE", "daveok"))
    p.add_argument("--databricks-host", default=os.environ.get("DATABRICKS_HOST", ""))
    args = p.parse_args()

    if not args.admin_user or not args.admin_password:
        print(
            "▸ LAKEBASE_USER/LAKEBASE_PASSWORD not set; generating short-lived admin credential from Databricks profile..."
        )
        try:
            auto_user, auto_password = _autogenerate_admin_credential(
                profile=args.databricks_profile,
                host=args.databricks_host or None,
                instance_name=args.instance_name,
            )
            args.admin_user = auto_user
            args.admin_password = auto_password
            print(f"  Using generated credential for: {args.admin_user}")
        except Exception as e:
            print(
                "✘ Missing Lakebase admin credentials and auto-generation failed. "
                "Set LAKEBASE_USER and LAKEBASE_PASSWORD explicitly.",
                file=sys.stderr,
            )
            print(f"  Reason: {e}", file=sys.stderr)
            return 1

    connector_sp_app_id = args.connector_sp_application_id or _read_profile_client_id(args.connector_sp_profile)
    if not connector_sp_app_id:
        print(
            "✘ Could not resolve connector SP application ID. Set SP_APPLICATION_ID "
            "or ensure client_id exists in the SP profile.",
            file=sys.stderr,
        )
        return 1

    artifact = Path(args.artifact_path)
    prior_artifact = _read_env_file(artifact)
    prior_password = ""
    if prior_artifact.get("LAKEBASE_USER") == args.connector_role_name:
        prior_password = prior_artifact.get("LAKEBASE_PASSWORD", "")

    # Keep existing connector password across idempotent reruns unless explicitly overridden.
    connector_password = args.connector_role_password or prior_password or secrets.token_urlsafe(28)

    print("▸ Resolving Lakebase instance...")
    instance = _ensure_instance(
        profile=args.databricks_profile,
        host=args.databricks_host or None,
        instance_name=args.instance_name,
        capacity=args.instance_capacity,
    )
    instance_host = os.environ.get("LAKEBASE_HOST") or _resolve_instance_host(instance)
    if not instance_host:
        print(
            "✘ Could not determine Lakebase host from instance output. "
            "Set LAKEBASE_HOST and retry.",
            file=sys.stderr,
        )
        return 1

    print(f"▸ Connecting to Lakebase admin endpoint: {instance_host}:{args.admin_port}")
    admin_conn = connect_postgres(
        host=instance_host,
        port=args.admin_port,
        database=DEFAULT_DB,
        user=args.admin_user,
        password=args.admin_password,
    )
    try:
        created_db = ensure_database(admin_conn, args.database_name)
        print(f"{'Created' if created_db else 'Using'} database: {args.database_name}")
    finally:
        admin_conn.close()

    db_conn = connect_postgres(
        host=instance_host,
        port=args.admin_port,
        database=args.database_name,
        user=args.admin_user,
        password=args.admin_password,
    )
    try:
        print("▸ Ensuring table objects from onboarding/lakebase/create_raw_tags.sql")
        apply_sql_file(db_conn, REPO_ROOT / "onboarding" / "lakebase" / "create_raw_tags.sql")

        print(f"▸ Ensuring connector role: {args.connector_role_name}")
        created_role = ensure_login_role(db_conn, args.connector_role_name, connector_password)
        print(f"{'Created' if created_role else 'Updated'} connector role password")

        with db_conn.cursor() as cur:
            cur.execute(f'GRANT CONNECT ON DATABASE "{args.database_name}" TO "{args.connector_role_name}"')
        grant_connector_privileges(
            db_conn,
            role_name=args.connector_role_name,
            schema_name=args.database_schema,
            table_name=args.table_name,
        )

        w = WorkspaceClient(profile=args.databricks_profile)
        app_sp_app_id = _app_service_principal_application_id(w, args.app_name)
        if app_sp_app_id:
            print(f"▸ Granting app query privileges to app role: {app_sp_app_id}")
            grant_app_query_privileges(
                db_conn,
                app_role_name=app_sp_app_id,
                schema_name=args.database_schema,
                table_name=args.table_name,
            )
        else:
            print("WARN: Could not resolve app service principal application_id, skipped app PostgreSQL grants")

        if args.warehouse_id:
            print(f"▸ Applying UC grants for connector SP on {args.catalog}.{args.schema}")
            run_uc_grants(
                w,
                connector_sp_app_id,
                args.catalog,
                args.schema,
                args.warehouse_id,
            )
            if app_sp_app_id:
                print(f"▸ Applying UC grants for app SP on {args.catalog}.{args.schema}")
                run_uc_grants(
                    w,
                    app_sp_app_id,
                    args.catalog,
                    args.schema,
                    args.warehouse_id,
                )
        else:
            print("WARN: DATABRICKS_WAREHOUSE_ID not set; skipped UC grants")
    finally:
        db_conn.close()

    artifact.write_text(
        "\n".join(
            [
                f"LAKEBASE_HOST={instance_host}",
                f"LAKEBASE_PORT={args.admin_port}",
                f"LAKEBASE_DATABASE={args.database_name}",
                f"LAKEBASE_USER={args.connector_role_name}",
                f"LAKEBASE_PASSWORD={connector_password}",
                f"LAKEBASE_TABLE={args.table_name}",
                "",
            ]
        )
    )
    print(f"✔ Wrote connector artifact: {artifact}")
    print("  Use with gateway configure targets for Lakebase mode.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
