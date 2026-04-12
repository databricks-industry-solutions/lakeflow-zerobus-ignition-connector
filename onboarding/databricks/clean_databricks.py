#!/usr/bin/env python3
"""Drop catalog (CASCADE), delete SDP pipeline, training job, and zerobus app for a clean Databricks reset.

Run with the same profile used for setup (e.g. your user profile with metastore/admin rights).
After this, run make db-setup-sql (or make bootstrap-83) to recreate everything.

Usage:
  DATABRICKS_CONFIG_PROFILE=daveok uv run --with databricks-sdk python onboarding/databricks/clean_databricks.py

Optional env:
  CATALOG (default: agl_demo)
  PIPELINE_NAME (default: [production] agl-etl)
  JOB_NAME (default: [production] agl-train-health-model)
  DATABRICKS_WAREHOUSE_ID (default: e4082fdb7ea19a15)

Flags:
  --skip-catalog   Do not drop the catalog (e.g. keep data, only remove pipeline + app + job).
  --skip-pipeline  Do not delete the pipeline.
  --skip-app       Do not delete the app.
  --skip-job       Do not delete the training job.
"""

from __future__ import annotations

import argparse
import os
import sys

from databricks.sdk import WorkspaceClient

DEFAULT_CATALOG = "agl_demo"
DEFAULT_PIPELINE_NAME = "[production] agl-etl"
DEFAULT_JOB_NAME = "[production] agl-train-health-model"
DEFAULT_WAREHOUSE_ID = "e4082fdb7ea19a15"
APP_NAME = "zerobus-ignition-agl"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean Databricks: drop catalog CASCADE, delete pipeline and app."
    )
    parser.add_argument(
        "--skip-catalog",
        action="store_true",
        help="Do not drop the catalog (only delete pipeline + app).",
    )
    parser.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Do not delete the pipeline.",
    )
    parser.add_argument(
        "--skip-app",
        action="store_true",
        help="Do not delete the app.",
    )
    parser.add_argument(
        "--skip-job",
        action="store_true",
        help="Do not delete the training job.",
    )
    args = parser.parse_args()

    profile = os.environ.get("DATABRICKS_CONFIG_PROFILE", "daveok")
    catalog = os.environ.get("CATALOG", DEFAULT_CATALOG)
    pipeline_name = os.environ.get("PIPELINE_NAME", DEFAULT_PIPELINE_NAME)
    job_name = os.environ.get("JOB_NAME", DEFAULT_JOB_NAME)
    warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", DEFAULT_WAREHOUSE_ID)

    w = WorkspaceClient(profile=profile)

    if not args.skip_catalog:
        print(f"▸ Dropping catalog {catalog} (CASCADE)...")
        try:
            resp = w.statement_execution.execute_statement(
                warehouse_id=warehouse_id,
                statement=f"DROP CATALOG IF EXISTS {catalog} CASCADE",
                wait_timeout="50s",  # API allows 0 or 5–50s
            )
            status = getattr(resp, "status", None)
            state = getattr(status, "state", None) if status else None
            ok = state is not None and (
                state == "SUCCEEDED" or str(state).endswith("SUCCEEDED")
            )
            if not ok:
                msg = getattr(status, "message", "") if status else ""
                print(f"   Failed: state={state} message={msg}", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"   Failed: {e}", file=sys.stderr)
            return 1
        print(f"   Dropped catalog {catalog}")
    else:
        print("▸ Skipping catalog drop (--skip-catalog)")

    if not args.skip_pipeline:
        pipeline_id = None
        for p in w.pipelines.list_pipelines():
            if p.name == pipeline_name:
                pipeline_id = p.pipeline_id
                break
        if pipeline_id:
            print(f"▸ Deleting pipeline '{pipeline_name}' (id={pipeline_id})...")
            try:
                w.pipelines.delete(pipeline_id=pipeline_id)
                print(f"   Deleted pipeline {pipeline_name}")
            except Exception as e:
                print(f"   Failed: {e}", file=sys.stderr)
                return 1
        else:
            print(f"   Pipeline '{pipeline_name}' not found (skip)")
    else:
        print("▸ Skipping pipeline delete (--skip-pipeline)")

    if not args.skip_app:
        try:
            w.apps.delete(name=APP_NAME)
            print(f"▸ Deleted app '{APP_NAME}'")
        except Exception as e:
            err_str = str(e).lower()
            if "not found" in err_str or "404" in err_str or "does not exist" in err_str:
                print(f"   App '{APP_NAME}' not found (skip)")
            else:
                print(f"   Failed: {e}", file=sys.stderr)
                return 1
    else:
        print("▸ Skipping app delete (--skip-app)")

    if not args.skip_job:
        job_id = None
        for j in w.jobs.list():
            if j.settings and j.settings.name == job_name:
                job_id = j.job_id
                break
        if job_id:
            print(f"▸ Deleting job '{job_name}' (id={job_id})...")
            try:
                w.jobs.delete(job_id=job_id)
                print(f"   Deleted job {job_name}")
            except Exception as e:
                print(f"   Failed: {e}", file=sys.stderr)
                return 1
        else:
            print(f"   Job '{job_name}' not found (skip)")
    else:
        print("▸ Skipping job delete (--skip-job)")

    print("✔ Databricks clean complete. Run make db-setup-sql (or make bootstrap-83) to recreate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
