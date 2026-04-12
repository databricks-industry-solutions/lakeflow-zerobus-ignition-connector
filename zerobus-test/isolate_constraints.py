#!/usr/bin/env python3
"""
Isolate which Delta table features Zerobus Ingest supports.

Creates table variants with different constraints/features, then tries
to create a Zerobus JSON stream to each. Reports pass/fail for each.

Phase 1 (constraint isolation):
  v0_clean       -- no PK, no NOT NULL, no CDF, no CLUSTER BY
  v1_notnull     -- add NOT NULL on event_id/event_time/tag_path/tag_provider
  v2_pk          -- add PRIMARY KEY (event_id)
  v3_cluster     -- add CLUSTER BY (event_time, tag_path)
  v4_cdf         -- add CDF (delta.enableChangeDataFeed)
  v5_all         -- all constraints (same as production raw_tags)

Phase 2 (partitioning + generated columns):
  v6_partition      -- PARTITIONED BY (tag_provider) on existing column
  v7_generated      -- GENERATED ALWAYS AS column (event_day), no partition
  v8_gen_partition  -- GENERATED ALWAYS AS + PARTITIONED BY (event_day)
  v9_part_regular   -- PARTITIONED BY (event_day) where writer provides value

For each variant: CREATE TABLE, GRANT SP, try stream creation, report pass/fail.

Usage (from repo root):
  export $(grep -v '^#' .env | xargs)
  cd zerobus-test && uv run --with databricks-sdk python isolate_constraints.py
"""

import os
import sys
import time
import uuid

# Databricks SDK for table creation
try:
    from databricks.sdk import WorkspaceClient
except ImportError:
    sys.exit("Install databricks-sdk: uv add databricks-sdk (or run from repo root with uv run --with databricks-sdk)")

from zerobus.sdk.sync import ZerobusSdk
from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties

# --- Configuration (ZEROBUS_ENDPOINT or WORKSPACE_ID+DATABRICKS_REGION from .env) ---
def _zerobus_endpoint() -> str:
    e = os.environ.get("ZEROBUS_ENDPOINT")
    if e:
        return e
    wid, reg = os.environ.get("WORKSPACE_ID"), os.environ.get("DATABRICKS_REGION")
    if wid and reg:
        return f"{wid}.zerobus.{reg}.azuredatabricks.net"
    return "7405607216190670.zerobus.eastus2.azuredatabricks.net"


SERVER_ENDPOINT = _zerobus_endpoint()
WORKSPACE_URL = os.environ.get("DATABRICKS_HOST", "https://adb-7405607216190670.10.azuredatabricks.net")
CLIENT_ID = os.environ.get("DATABRICKS_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
CATALOG = os.environ.get("CATALOG", "agl_demo")
SCHEMA = os.environ.get("SCHEMA", "ot")
SP_ID = os.environ.get("SP_APPLICATION_ID", "66c066ad-d5a9-496f-8da5-6d7bc2f5d954")
DATABRICKS_WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "e4082fdb7ea19a15")
DATABRICKS_CONFIG_PROFILE = os.environ.get("DATABRICKS_CONFIG_PROFILE", "daveok")
# -----------------------------------------------------------------------------

# Base columns (no constraints)
BASE_COLUMNS = """
  event_id              STRING,
  event_time            BIGINT,
  tag_path              STRING,
  tag_provider          STRING,
  numeric_value         DOUBLE,
  string_value          STRING,
  boolean_value         BOOLEAN,
  quality               STRING,
  quality_code          INT,
  source_system         STRING,
  ingestion_timestamp   BIGINT,
  data_type             STRING,
  alarm_state           STRING,
  alarm_priority        INT,
  sdt_compressed        BOOLEAN,
  compression_ratio     DOUBLE,
  sdt_enabled           BOOLEAN,
  batch_bytes_sent      BIGINT
""".strip()

NOTNULL_COLUMNS = BASE_COLUMNS.replace(
    "event_id              STRING",
    "event_id              STRING      NOT NULL"
).replace(
    "event_time            BIGINT",
    "event_time            BIGINT      NOT NULL"
).replace(
    "tag_path              STRING,\n  tag_provider",
    "tag_path              STRING      NOT NULL,\n  tag_provider"
).replace(
    "tag_provider          STRING",
    "tag_provider          STRING      NOT NULL"
)

# --- Phase 2 columns: add generated/partition columns to base ---

# For v6: partition on existing column (tag_provider) -- no schema change needed
# For v7: add a generated column (event_day) computed from event_time
GENERATED_COL = ",\n  event_day DATE GENERATED ALWAYS AS (CAST(FROM_UNIXTIME(event_time / 1000000) AS DATE))"
# For v9: add a regular event_day column the writer provides
REGULAR_DAY_COL = ",\n  event_day DATE"

# Variant definitions: (suffix, columns, extra_clauses, tblproperties, record_override)
# record_override: None = use base 18-col record; dict = merge extra keys into base record
VARIANTS = [
    # --- Phase 1: constraint isolation (proven results, re-run for completeness) ---
    ("v0_clean",   BASE_COLUMNS,    "",                                   "", None),
    ("v1_notnull", NOTNULL_COLUMNS, "",                                   "", None),
    ("v2_pk",      BASE_COLUMNS + ",\n  CONSTRAINT pk PRIMARY KEY (event_id)", "", "", None),
    ("v3_cluster", BASE_COLUMNS,    "CLUSTER BY (event_time, tag_path)",  "", None),
    ("v4_cdf",     BASE_COLUMNS,    "",                                   "TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')", None),
    ("v5_all",     NOTNULL_COLUMNS + ",\n  CONSTRAINT pk PRIMARY KEY (event_id)",
                                    "CLUSTER BY (event_time, tag_path)",  "TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')", None),
    # --- Phase 2: partitioning + generated columns ---
    ("v6_partition",     BASE_COLUMNS,                    "PARTITIONED BY (tag_provider)", "", None),
    ("v7_generated",     BASE_COLUMNS + GENERATED_COL,    "",                              "", None),  # omit event_day from record
    ("v8_gen_partition",  BASE_COLUMNS + GENERATED_COL,    "PARTITIONED BY (event_day)",   "", None),  # generated + partitioned
    ("v9_part_regular",  BASE_COLUMNS + REGULAR_DAY_COL,  "PARTITIONED BY (event_day)",    "",
     {"event_day": "2026-02-14"}),  # writer provides event_day as string
    ("v9b_part_epoch",   BASE_COLUMNS + REGULAR_DAY_COL,  "PARTITIONED BY (event_day)",    "",
     {"event_day": 20498}),  # writer provides event_day as epoch days (int)
    ("v9c_part_int",     BASE_COLUMNS + ",\n  event_day INT",  "PARTITIONED BY (event_day)",    "",
     {"event_day": 20498}),  # INT partition column instead of DATE
]


def run_sql(w, stmt: str, desc: str) -> bool:
    try:
        resp = w.statement_execution.execute_statement(
            warehouse_id=DATABRICKS_WAREHOUSE_ID,
            statement=stmt.strip(),
            wait_timeout="30s",
        )
        state = getattr(getattr(resp, "status", None), "state", None)
        ok = state is not None and (str(state) == "SUCCEEDED" or str(state).endswith("SUCCEEDED"))
        if not ok:
            err = getattr(getattr(resp, "status", None), "error", None)
            print(f"    SQL FAILED ({desc}): state={state} error={err}")
        return ok
    except Exception as e:
        print(f"    SQL FAILED ({desc}): {e}")
        return False


def make_base_record() -> dict:
    """Build the standard 18-column JSON record."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_time": int(time.time() * 1_000_000),
        "tag_path": "[test]constraint_test",
        "tag_provider": "test",
        "numeric_value": 42.0,
        "string_value": "",
        "boolean_value": False,
        "quality": "Good",
        "quality_code": 192,
        "source_system": "constraint-isolator",
        "ingestion_timestamp": int(time.time() * 1_000_000),
        "data_type": "DOUBLE",
        "alarm_state": "",
        "alarm_priority": 0,
        "sdt_compressed": False,
        "compression_ratio": 0.0,
        "sdt_enabled": False,
        "batch_bytes_sent": 0,
    }


def test_stream(table_name: str, record_override: dict | None = None) -> tuple[bool, str]:
    """Try to create a JSON stream to the table. Returns (success, message)."""
    try:
        sdk = ZerobusSdk(SERVER_ENDPOINT, WORKSPACE_URL)
        table_properties = TableProperties(table_name)
        options = StreamConfigurationOptions(record_type=RecordType.JSON)
        stream = sdk.create_stream(CLIENT_ID, CLIENT_SECRET, table_properties, options)
        # Send one record to confirm it works end-to-end
        record = make_base_record()
        if record_override:
            record.update(record_override)
        ack = stream.ingest_record(record)
        ack.wait_for_ack()
        stream.close()
        return True, "stream created + 1 record ingested"
    except Exception as e:
        msg = str(e)
        if "1521" in msg:
            return False, "FAILED: 1521 (stream creation rejected)"
        return False, f"FAILED: {msg[:150]}"


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        sys.exit("Set DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET in environment.")

    print(f"=== Zerobus 1521 Constraint Isolation ===")
    print(f"Catalog: {CATALOG}, Schema: {SCHEMA}, SP: {SP_ID}")
    print(f"Endpoint: {SERVER_ENDPOINT}")
    print(f"Workspace: {WORKSPACE_URL}")
    print()

    w = WorkspaceClient(profile=DATABRICKS_CONFIG_PROFILE)

    results = []
    for variant in VARIANTS:
        suffix, columns, extra, tblprops, record_override = variant
        table_name = f"{CATALOG}.{SCHEMA}.zb_test_{suffix}"
        print(f"--- {suffix} ({table_name}) ---")

        # Drop if exists (clean slate)
        run_sql(w, f"DROP TABLE IF EXISTS {table_name}", "DROP")

        # Create
        ddl = f"CREATE TABLE {table_name} (\n{columns}\n)\n{extra}\n{tblprops}"
        if not run_sql(w, ddl, "CREATE"):
            results.append((suffix, "SKIP", "table creation failed"))
            continue

        # Grant SP
        if not run_sql(w, f"GRANT MODIFY, SELECT ON TABLE {table_name} TO `{SP_ID}`", "GRANT"):
            results.append((suffix, "SKIP", "grant failed"))
            continue

        # Test Zerobus stream
        extra_info = ""
        if record_override:
            extra_info = f" (record adds: {list(record_override.keys())})"
        print(f"    Testing Zerobus stream...{extra_info}")
        ok, msg = test_stream(table_name, record_override)
        status = "PASS" if ok else "FAIL"
        print(f"    {status}: {msg}")
        results.append((suffix, status, msg))

        # Cleanup
        run_sql(w, f"DROP TABLE IF EXISTS {table_name}", "DROP cleanup")
        print()

    # Summary
    print("=" * 72)
    print("RESULTS SUMMARY")
    print("=" * 72)
    constraints = {
        "v0_clean":        "none (bare columns)",
        "v1_notnull":      "NOT NULL on 4 cols",
        "v2_pk":           "PRIMARY KEY (event_id)",
        "v3_cluster":      "CLUSTER BY (event_time, tag_path)",
        "v4_cdf":          "CDF enabled",
        "v5_all":          "NOT NULL + PK + CLUSTER BY + CDF (prod)",
        "v6_partition":    "PARTITIONED BY (tag_provider)",
        "v7_generated":    "GENERATED ALWAYS AS (event_day)",
        "v8_gen_partition": "GENERATED + PARTITIONED BY (event_day)",
        "v9_part_regular": "PARTITIONED BY (event_day DATE) string val",
        "v9b_part_epoch":  "PARTITIONED BY (event_day DATE) epoch-days int",
        "v9c_part_int":    "PARTITIONED BY (event_day INT) epoch-days int",
    }
    print(f"\n  Phase 1: Constraint isolation")
    print(f"  {'-' * 68}")
    for suffix, status, msg in results:
        if not suffix.startswith("v6") and not suffix.startswith("v7") and not suffix.startswith("v8") and not suffix.startswith("v9"):
            print(f"  {status:4s}  {suffix:<16s}  {constraints.get(suffix, ''):<45s}  {msg}")

    print(f"\n  Phase 2: Partitioning + generated columns")
    print(f"  {'-' * 68}")
    for suffix, status, msg in results:
        if suffix.startswith("v6") or suffix.startswith("v7") or suffix.startswith("v8") or suffix.startswith("v9"):
            print(f"  {status:4s}  {suffix:<16s}  {constraints.get(suffix, ''):<45s}  {msg}")

    any_fail = any(s == "FAIL" for _, s, _ in results)
    if any_fail:
        print("\n>>> One or more variants FAILED. See above for which features Zerobus rejects.")
    else:
        print("\n>>> All variants PASSED. All tested features are Zerobus-compatible.")

    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
