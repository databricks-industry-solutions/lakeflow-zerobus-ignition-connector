#!/usr/bin/env python3
"""Deploy and run a test SDP pipeline to check GENERATED ALWAYS AS vs date_trunc.

Creates a throwaway pipeline with 3 SQL files:
  - test_generated.sql  -- GENERATED ALWAYS AS in streaming table DDL
  - test_date_trunc.sql -- date_trunc / DATE() in SELECT (standard pattern)
  - test_mv_trunc.sql   -- materialized view with time-truncated columns

Reports which tables succeeded and which failed, then cleans up.

Usage (from repo root):
  cd zerobus-test/sdp_generated_col_test
  uv run --with databricks-sdk python run_test_pipeline.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import pipelines as pipelines_api

# --- Configuration -----------------------------------------------------------
PROFILE = os.environ.get("DATABRICKS_CONFIG_PROFILE", "daveok")
CATALOG = os.environ.get("CATALOG", "agl_demo")
SCHEMA = os.environ.get("SCHEMA", "ot")
PIPELINE_NAME = "[test] sdp-generated-col-test"
WORKSPACE_FOLDER = "/Users/david.okeeffe@databricks.com/sdp_generated_col_test"
TIMEOUT_SECONDS = 600  # 10 minutes
# -----------------------------------------------------------------------------

SQL_FILES = ["test_generated.sql", "test_date_trunc.sql", "test_mv_trunc.sql"]


def upload_sql_files(w: WorkspaceClient) -> list[str]:
    """Upload SQL files to workspace, return list of workspace paths."""
    script_dir = Path(__file__).parent
    paths = []
    for fname in SQL_FILES:
        local = script_dir / fname
        remote = f"{WORKSPACE_FOLDER}/{fname}"
        print(f"  Uploading {fname} -> {remote}")
        content = local.read_bytes()
        try:
            w.workspace.mkdirs(WORKSPACE_FOLDER)
        except Exception:
            pass  # already exists
        import base64
        from databricks.sdk.service.workspace import ImportFormat, Language
        w.workspace.import_(
            path=remote,
            content=base64.b64encode(content).decode(),
            format=ImportFormat.SOURCE,
            language=Language.SQL,
            overwrite=True,
        )
        paths.append(remote)
    return paths


def find_pipeline(w: WorkspaceClient, name: str) -> str | None:
    """Find existing pipeline by name."""
    for p in w.pipelines.list_pipelines():
        if p.name == name:
            return p.pipeline_id
    return None


def create_or_update_pipeline(w: WorkspaceClient, file_paths: list[str]) -> str:
    """Create or update the test pipeline, return pipeline_id."""
    libs = [
        pipelines_api.PipelineLibrary(file=pipelines_api.FileLibrary(path=p))
        for p in file_paths
    ]

    existing_id = find_pipeline(w, PIPELINE_NAME)
    if existing_id:
        print(f"  Updating existing pipeline: {existing_id}")
        w.pipelines.update(
            pipeline_id=existing_id,
            name=PIPELINE_NAME,
            catalog=CATALOG,
            schema=SCHEMA,
            libraries=libs,
            serverless=True,
            development=True,  # dev mode for fast iteration
            channel="PREVIEW",
            photon=True,
            continuous=False,
        )
        return existing_id
    else:
        print(f"  Creating new pipeline: {PIPELINE_NAME}")
        result = w.pipelines.create(
            name=PIPELINE_NAME,
            catalog=CATALOG,
            schema=SCHEMA,
            libraries=libs,
            serverless=True,
            development=True,
            channel="PREVIEW",
            photon=True,
            continuous=False,
        )
        return result.pipeline_id


def run_pipeline(w: WorkspaceClient, pipeline_id: str) -> dict:
    """Start a full refresh and wait for completion. Returns update info."""
    print(f"  Starting full refresh...")
    run = w.pipelines.start_update(
        pipeline_id=pipeline_id,
        full_refresh=True,
    )
    update_id = run.update_id
    print(f"  Update ID: {update_id}")

    start_time = time.time()
    while time.time() - start_time < TIMEOUT_SECONDS:
        update = w.pipelines.get_update(pipeline_id=pipeline_id, update_id=update_id)
        state = str(update.update.state) if update.update else "UNKNOWN"
        elapsed = int(time.time() - start_time)
        print(f"  [{elapsed}s] State: {state}")

        if state in ("COMPLETED", "UpdateInfoState.COMPLETED"):
            return {"state": "COMPLETED", "elapsed": elapsed}
        elif state in ("FAILED", "UpdateInfoState.FAILED"):
            return {"state": "FAILED", "elapsed": elapsed}
        elif state in ("CANCELED", "UpdateInfoState.CANCELED"):
            return {"state": "CANCELED", "elapsed": elapsed}

        time.sleep(10)

    return {"state": "TIMEOUT", "elapsed": int(time.time() - start_time)}


def get_errors(w: WorkspaceClient, pipeline_id: str) -> list[str]:
    """Get error events from the pipeline."""
    errors = []
    for event in w.pipelines.list_pipeline_events(
        pipeline_id=pipeline_id,
        max_results=50,
        order_by=["timestamp desc"],
    ):
        if event.level and "ERROR" in str(event.level):
            msg = event.message or ""
            if event.error and event.error.exceptions:
                for ex in event.error.exceptions:
                    if ex.message:
                        msg += f"\n  {ex.message}"
            errors.append(msg)
    return errors


def check_tables(w: WorkspaceClient) -> dict[str, str]:
    """Check which test tables exist and have data."""
    test_tables = {
        "test_generated": "GENERATED ALWAYS AS",
        "test_date_trunc": "date_trunc in SELECT",
        "test_mv_daily": "MV with time-truncated columns",
    }
    results = {}
    for tbl, desc in test_tables.items():
        fqn = f"{CATALOG}.{SCHEMA}.{tbl}"
        try:
            resp = w.statement_execution.execute_statement(
                warehouse_id=os.environ.get("DATABRICKS_WAREHOUSE_ID", "e4082fdb7ea19a15"),
                statement=f"SELECT COUNT(*) AS cnt FROM {fqn}",
                wait_timeout="30s",
            )
            state = str(getattr(getattr(resp, "status", None), "state", None))
            if "SUCCEEDED" in state:
                rows = resp.result.data_array if resp.result else []
                cnt = rows[0][0] if rows else "0"
                results[tbl] = f"PASS ({cnt} rows) -- {desc}"
            else:
                err = getattr(getattr(resp, "status", None), "error", None)
                results[tbl] = f"FAIL (query error: {err}) -- {desc}"
        except Exception as e:
            results[tbl] = f"FAIL (table not found: {str(e)[:80]}) -- {desc}"
    return results


def cleanup(w: WorkspaceClient, pipeline_id: str):
    """Delete the test pipeline and tables."""
    print("\n--- Cleanup ---")
    wid = os.environ.get("DATABRICKS_WAREHOUSE_ID", "e4082fdb7ea19a15")
    for tbl in ["test_generated", "test_date_trunc", "test_mv_daily"]:
        fqn = f"{CATALOG}.{SCHEMA}.{tbl}"
        try:
            w.statement_execution.execute_statement(
                warehouse_id=wid,
                statement=f"DROP TABLE IF EXISTS {fqn}",
                wait_timeout="30s",
            )
            print(f"  Dropped {fqn}")
        except Exception:
            try:
                w.statement_execution.execute_statement(
                    warehouse_id=wid,
                    statement=f"DROP VIEW IF EXISTS {fqn}",
                    wait_timeout="30s",
                )
                print(f"  Dropped view {fqn}")
            except Exception:
                pass

    try:
        w.pipelines.delete(pipeline_id=pipeline_id)
        print(f"  Deleted pipeline {pipeline_id}")
    except Exception as e:
        print(f"  Failed to delete pipeline: {e}")

    try:
        w.workspace.delete(WORKSPACE_FOLDER, recursive=True)
        print(f"  Deleted workspace folder {WORKSPACE_FOLDER}")
    except Exception:
        pass


def main() -> int:
    print("=== SDP Generated Column Test ===\n")
    w = WorkspaceClient(profile=PROFILE)

    print("1. Uploading SQL files...")
    file_paths = upload_sql_files(w)

    print("\n2. Creating test pipeline...")
    pipeline_id = create_or_update_pipeline(w, file_paths)
    print(f"  Pipeline ID: {pipeline_id}")

    print("\n3. Running pipeline (full refresh)...")
    result = run_pipeline(w, pipeline_id)
    print(f"  Final state: {result['state']} ({result['elapsed']}s)")

    if result["state"] != "COMPLETED":
        print("\n4. Pipeline errors:")
        errors = get_errors(w, pipeline_id)
        for i, err in enumerate(errors[:10]):
            print(f"  [{i+1}] {err}")
    else:
        print("\n4. No errors (pipeline completed)")

    print("\n5. Checking output tables...")
    tables = check_tables(w)
    for tbl, status in tables.items():
        print(f"  {tbl}: {status}")

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for tbl, status in tables.items():
        marker = "PASS" if status.startswith("PASS") else "FAIL"
        print(f"  {marker}  {tbl:<20s}  {status}")

    cleanup(w, pipeline_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
