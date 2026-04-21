#!/usr/bin/env python3
"""Run health_scores verification query and report whether the pipeline produced health scores.

Executes pipelines/sdp/verify_health_scores.sql (with catalog/schema substitution),
then checks that we have rows with health_score. Exits 0 if health_scores has data, 1 otherwise.

Usage:
  DATABRICKS_CONFIG_PROFILE=daveok uv run --with databricks-sdk python onboarding/databricks/verify_ml_health.py

Optional env:
  CATALOG (default: ot_demo)
  SCHEMA (default: ot)
  DATABRICKS_WAREHOUSE_ID (default: e4082fdb7ea19a15)
"""

from __future__ import annotations

import os
import sys

from databricks.sdk import WorkspaceClient

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
VERIFY_SQL_PATH = os.path.join(REPO_ROOT, "pipelines/sdp/verify_health_scores.sql")
DEFAULT_WAREHOUSE_ID = "e4082fdb7ea19a15"
DEFAULT_CATALOG = "ot_demo"
DEFAULT_SCHEMA = "ot"


def main() -> int:
    profile = os.environ.get("DATABRICKS_CONFIG_PROFILE", "daveok")
    warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", DEFAULT_WAREHOUSE_ID)
    catalog = os.environ.get("CATALOG", DEFAULT_CATALOG)
    schema = os.environ.get("SCHEMA", DEFAULT_SCHEMA)

    if not os.path.isfile(VERIFY_SQL_PATH):
        print(f"Not found: {VERIFY_SQL_PATH}", file=sys.stderr)
        return 1

    with open(VERIFY_SQL_PATH) as f:
        sql = f.read()
    sql = sql.replace("__CATALOG__", catalog).replace("__SCHEMA__", schema).strip()

    w = WorkspaceClient(profile=profile)
    try:
        resp = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            catalog=catalog,
            schema=schema,
            statement=sql,
            wait_timeout="30s",
        )
    except Exception as e:
        print(f"Statement execution failed: {e}", file=sys.stderr)
        return 1

    if not resp.status:
        print("No status in response", file=sys.stderr)
        return 1
    state = str(resp.status.state)
    if not state.endswith("SUCCEEDED"):
        msg = getattr(resp.status, "message", "") or ""
        err = getattr(resp.status, "error", None)
        err_msg = getattr(err, "message", str(err)) if err else ""
        print(f"Query failed: state={state} {msg} {err_msg}", file=sys.stderr)
        return 1

    if not resp.manifest or not resp.result or not resp.result.data_array:
        print("No rows returned. Pipeline may not have run yet or health_scores is empty.", file=sys.stderr)
        return 1

    columns = [c.name for c in resp.manifest.schema.columns]
    if "health_score" not in columns:
        print("Column health_score not in result.", file=sys.stderr)
        return 1

    rows = resp.result.data_array
    print(f"OK: health_scores has data. {len(rows)} row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
