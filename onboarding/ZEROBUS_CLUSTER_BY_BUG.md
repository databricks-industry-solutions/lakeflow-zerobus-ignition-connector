# Zerobus Ingest: Liquid Clustering causes INTERNAL/1521

**Date:** 2026-02-14
**Status:** Undocumented limitation (not in [Zerobus limitations page](https://docs.databricks.com/aws/en/ingestion/zerobus-limits))
**Affects:** All Zerobus Ingest SDKs (Python, Java, Go, Rust, TypeScript), all record types (JSON + Protobuf)
**Workspace:** Azure East US 2 (`adb-7405607216190670`), Python SDK 0.2.0, Java SDK 0.1.0

## Problem

Zerobus Ingest stream creation fails with `INTERNAL: Error Code 1521, Error State 0` when the target Delta table has **liquid clustering** (`CLUSTER BY`) enabled. The error is opaque -- neither the gRPC response nor Databricks docs explain what 1521 means.

```
Stream creation failed: com.databricks.zerobus.ZerobusException:
  Stream failed: INTERNAL: Internal error. Error Code: 1521, Error State: 0.
```

## Root cause

Delta tables created with `CLUSTER BY (col1, col2)` set the `liquid` clustering writer feature in the table's protocol. Zerobus Ingest does not support this Delta writer feature and rejects stream creation at the server side.

This is NOT caused by:
- Invalid credentials (SP OAuth works; `make db-check-sp` passes)
- Missing UC grants (SP has `MODIFY`, `SELECT`)
- Schema mismatch (proto and table columns match exactly)
- NOT NULL constraints, PRIMARY KEY constraints, or Change Data Feed

## Fix

Remove liquid clustering from the target table:

```sql
ALTER TABLE catalog.schema.raw_tags CLUSTER BY NONE;
```

Stream creation succeeds immediately after this (no gateway restart needed; the retry loop picks it up).

## Isolation methodology

Systematically tested 6 table variants with the Python Zerobus SDK (`RecordType.JSON`), same SP, same endpoint. Each variant was created, granted, tested, then dropped:

| Variant | Table features | Stream creation |
|---------|---------------|----------------|
| v0_clean | Bare columns only | **PASS** |
| v1_notnull | `NOT NULL` on 4 columns | **PASS** |
| v2_pk | `PRIMARY KEY (event_id)` | **PASS** |
| v3_cluster | `CLUSTER BY (event_time, tag_path)` | **FAIL (1521)** |
| v4_cdf | `delta.enableChangeDataFeed = true` | **PASS** |
| v5_all | NOT NULL + PK + CLUSTER BY + CDF | **FAIL (1521)** |

Only the variants containing `CLUSTER BY` failed. The isolation script is at `zerobus-test/isolate_constraints.py`.

## Mini repro

Requires: Databricks workspace with Zerobus enabled, a service principal with UC grants, Python 3.12+, `uv`.

### 1. Install SDK

```bash
mkdir zerobus-repro && cd zerobus-repro
uv init && uv add databricks-zerobus-ingest-sdk
```

### 2. Create two tables (one with CLUSTER BY, one without)

Run in a Databricks SQL editor or notebook as a user with CREATE TABLE:

```sql
-- Table WITHOUT clustering (control)
CREATE TABLE IF NOT EXISTS my_catalog.my_schema.zb_no_cluster (
  id STRING, value DOUBLE
);
GRANT MODIFY, SELECT ON TABLE my_catalog.my_schema.zb_no_cluster
  TO `<your-sp-application-id>`;

-- Table WITH clustering (test)
CREATE TABLE IF NOT EXISTS my_catalog.my_schema.zb_with_cluster (
  id STRING, value DOUBLE
) CLUSTER BY (id);
GRANT MODIFY, SELECT ON TABLE my_catalog.my_schema.zb_with_cluster
  TO `<your-sp-application-id>`;
```

### 3. Run the repro script

```python
"""Minimal repro: Zerobus 1521 with CLUSTER BY."""
import uuid
from zerobus.sdk.sync import ZerobusSdk
from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties

ENDPOINT  = "<workspace-id>.zerobus.<region>.azuredatabricks.net"
WORKSPACE = "https://adb-<workspace-id>.<suffix>.azuredatabricks.net"
CLIENT_ID = "<sp-application-id>"
SECRET    = "<sp-client-secret>"

sdk = ZerobusSdk(ENDPOINT, WORKSPACE)
options = StreamConfigurationOptions(record_type=RecordType.JSON)

for table in ["my_catalog.my_schema.zb_no_cluster",
              "my_catalog.my_schema.zb_with_cluster"]:
    print(f"\nTesting: {table}")
    try:
        stream = sdk.create_stream(
            CLIENT_ID, SECRET,
            TableProperties(table), options
        )
        stream.ingest_record({"id": str(uuid.uuid4()), "value": 42.0}).wait_for_ack()
        stream.close()
        print(f"  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
```

### Expected output

```
Testing: my_catalog.my_schema.zb_no_cluster
  PASS

Testing: my_catalog.my_schema.zb_with_cluster
  FAIL: Failed to create a stream: ... INTERNAL: Internal error. Error Code: 1521 ...
```

### 4. Cleanup

```sql
DROP TABLE IF EXISTS my_catalog.my_schema.zb_no_cluster;
DROP TABLE IF EXISTS my_catalog.my_schema.zb_with_cluster;
```

## Phase 2: Partitioning and generated columns (2026-02-14)

Extended the isolation test to determine if traditional partitioning and generated columns can replace liquid clustering for time-based data layout.

### Results

| Variant | Table features | Stream creation | Record ingest |
|---------|---------------|----------------|--------------|
| v6_partition | `PARTITIONED BY (tag_provider)` | **PASS** | **PASS** |
| v7_generated | `event_day DATE GENERATED ALWAYS AS (...)` | **FAIL (1015)** | N/A |
| v8_gen_partition | Generated + `PARTITIONED BY (event_day)` | **FAIL (1015)** | N/A |
| v9_part_regular | `PARTITIONED BY (event_day DATE)` + string value | **PASS** | **FAIL (4044)** |
| v9b_part_epoch | `PARTITIONED BY (event_day DATE)` + epoch-days int | **PASS** | **PASS** |
| v9c_part_int | `PARTITIONED BY (event_day INT)` + epoch-days int | **PASS** | **PASS** |

### Key findings

1. **Traditional partitioning WORKS** -- `PARTITIONED BY` on regular columns is fully supported.
2. **Generated columns DO NOT WORK** -- Zerobus explicitly rejects them: `Feature 'generatedColumns' is not supported. Error Code: 1015`. This is a clearer error than the 1521 for clustering.
3. **DATE columns need epoch-days integers** -- Sending `"2026-02-14"` as a string causes Error 4044 "invalid digit found in string". Sending `20498` (epoch days) works.
4. **INT partition columns work fine** -- An INT column with epoch-days is the simplest approach.

### Unsupported Delta features summary

| Delta Feature | Writer Version | Error | Supported? |
|---|---|---|---|
| Basic partitioning | 2 | -- | **Yes** |
| NOT NULL constraints | 2 | -- | **Yes** |
| Primary Key | 2 | -- | **Yes** |
| Change Data Feed | 4 | -- | **Yes** |
| Generated columns | 4 | 1015 (UNIMPLEMENTED) | **No** |
| Liquid clustering | 7 | 1521 (INTERNAL) | **No** |

## Recommendation: keep the landing table flat (no partitioning)

**Don't partition `raw_tags`.** Use liquid clustering on downstream tables instead.

### Why not partition the Zerobus landing table?

1. **Proto/mapper churn for marginal benefit.** Adding a partition column like `event_day` means changing `ot_event.proto`, the Java `OtEventMapper`, the Delta table DDL, and every deployment. That's a lot of moving parts for a bronze landing table that is rarely queried directly.

2. **Delta data skipping already handles time-range queries.** `event_time BIGINT` automatically gets per-file min/max statistics. Queries with `WHERE event_time BETWEEN x AND y` skip irrelevant Parquet files without partitioning. For append-only time-series data this is surprisingly effective — the files are naturally time-ordered because events arrive chronologically.

3. **Small-file anti-pattern.** OT data arrives continuously at sub-second intervals. Daily partitions with high-frequency tag changes produce many small files per partition, degrading read performance. You'd need scheduled `OPTIMIZE` jobs per partition to compact them — adding operational overhead.

4. **Liquid clustering support is likely coming.** The 1521 limitation is clearly a gap in the current Zerobus implementation, not a fundamental design decision. The Zerobus team is actively developing the product; liquid clustering support is a reasonable expectation. Adding partitioning now means a migration away from it later.

5. **The SDP pipeline already solves this.** `raw_tags` is the bronze landing zone — raw, append-only, optimized for write throughput. Silver and gold tables are written by Spark (not Zerobus), so they **can** use `CLUSTER BY (event_time, tag_path)`. The architecture is already "flat landing table → clustered downstream tables."

### Recommended architecture

```
Ignition → Zerobus → raw_tags (bronze, flat, no clustering)
                          │
                          ▼  (SDP streaming pipeline)
                      silver_tags (CLUSTER BY event_time, tag_path)
                          │
                          ▼
                      gold_metrics (CLUSTER BY event_time, site_id)
```

- **Bronze (`raw_tags`)**: No partitioning, no clustering. Zerobus writes here at full throughput. Delta data skipping on `event_time` handles time-range queries adequately.
- **Silver/Gold**: Written by Spark via the SDP pipeline. Free to use `CLUSTER BY`, `GENERATED ALWAYS AS`, or any Delta feature. This is where query performance optimizations belong.

## SDP pipeline: GENERATED ALWAYS AS vs date_trunc (2026-02-14)

Tested whether SDP (Spark Declarative Pipelines / DLT) can use `GENERATED ALWAYS AS` and `date_trunc` on downstream tables that read from the Zerobus landing table.

### Test setup

Deployed a throwaway pipeline (`[test] sdp-generated-col-test`) with 3 SQL files reading from `agl_demo.ot.raw_tags`:

| Test | SQL | Result |
|------|-----|--------|
| A: `GENERATED ALWAYS AS` | Streaming table with explicit DDL column `event_day DATE GENERATED ALWAYS AS (...)` | **PASS** (100 rows) |
| B: `date_trunc` in SELECT | Streaming table with `DATE(FROM_UNIXTIME(...))` and `DATE_TRUNC('HOUR', ...)` in SELECT, `CLUSTER BY (event_day)` | **PASS** (100 rows) |
| C: MV with truncated time | Materialized view with `DATE(FROM_UNIXTIME(...))`, `CLUSTER BY (event_day)` | **PASS** (216 rows) |

All three approaches work. The pipeline completed in 31 seconds.

### Why does GENERATED ALWAYS AS work in SDP but not in Zerobus?

The difference is **which writer** is creating the Delta files:

| | Zerobus Ingest | SDP / Spark |
|---|---|---|
| **Writer** | Custom Zerobus gRPC server | Apache Spark Delta writer |
| **Protocol support** | Limited: basic columns, NOT NULL, PK, CDF | Full: all Delta writer features |
| **Generated columns** | **Not supported** (Error 1015) | **Supported** (writer v4) |
| **Liquid clustering** | **Not supported** (Error 1521) | **Supported** (writer v7) |

### Recommendation: use date_trunc in SELECT, not GENERATED ALWAYS AS

Even though `GENERATED ALWAYS AS` works in SDP, **prefer `date_trunc` / `DATE()` in the SELECT**:

1. **Explicit > implicit.** The transformation logic is visible in the pipeline SQL, not hidden in table metadata.
2. **No protocol bump.** A regular column computed in the SELECT has no Delta protocol restrictions.
3. **Already the established pattern.** The existing `bronze_silver.py` computes `event_timestamp` via `F.to_timestamp(...)`.
4. **Composable.** Compute multiple time granularities in one SELECT:

```sql
CREATE OR REFRESH STREAMING TABLE silver_tags
CLUSTER BY (event_day, tag_path)
AS SELECT
  *,
  DATE(FROM_UNIXTIME(event_time / 1000000))                 AS event_day,
  DATE_TRUNC('HOUR', FROM_UNIXTIME(event_time / 1000000))   AS event_hour
FROM STREAM(agl_demo.ot.raw_tags);
```

Test script: `zerobus-test/sdp_generated_col_test/run_test_pipeline.py`

## References

- [Zerobus Ingest limitations](https://docs.databricks.com/aws/en/ingestion/zerobus-limits) -- does NOT mention CLUSTER BY
- [Zerobus Ingest usage](https://learn.microsoft.com/en-us/azure/databricks/ingestion/zerobus-ingest) -- table creation examples use no clustering
- [Liquid clustering docs](https://docs.databricks.com/aws/en/delta/clustering) -- no mention of Zerobus incompatibility
- This repo: `module/SCHEMA_ALIGNMENT.md`, `zerobus-test/isolate_constraints.py`
