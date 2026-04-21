# OTEvent protobuf ↔ Delta table schema alignment

The Zerobus connector sends `OTEvent` protobuf messages. The target Delta table (`raw_tags`) **must** match the proto in column names, order, and types for Zerobus to accept the stream. Mismatch can cause INTERNAL/1521.

## Field-by-field alignment

| Proto (ot_event.proto) | Delta (raw_tags) | Notes |
|------------------------|------------------------|-------|
| event_id string        | event_id STRING        | PK    |
| event_time int64       | event_time BIGINT      | **Microseconds** since Unix epoch (Java sends micros) |
| tag_path string        | tag_path STRING        |       |
| tag_provider string    | tag_provider STRING    |       |
| optional double numeric_value   | numeric_value DOUBLE   | `optional` — see below |
| optional string string_value    | string_value STRING    | `optional` — see below |
| optional bool boolean_value     | boolean_value BOOLEAN  | `optional` — see below |
| optional string quality         | quality STRING         | `optional` — see below |
| optional int32 quality_code     | quality_code INT       | `optional` — see below |
| source_system string   | source_system STRING   |       |
| ingestion_timestamp int64 | ingestion_timestamp BIGINT | **Microseconds** since epoch |
| data_type string       | data_type STRING       |       |
| optional string alarm_state     | alarm_state STRING     | `optional` — see below |
| optional int32 alarm_priority   | alarm_priority INT     | `optional` — see below |
| optional bool sdt_compressed    | sdt_compressed BOOLEAN | `optional` — see below |
| optional double compression_ratio | compression_ratio DOUBLE | `optional` — see below |
| optional bool sdt_enabled       | sdt_enabled BOOLEAN    | `optional` — see below |
| optional int64 batch_bytes_sent | batch_bytes_sent BIGINT | `optional` — see below |

### Why `optional`?

In proto3, fields at their default value (0, 0.0, false, "") are **not serialized** on the wire. Zerobus Ingest maps absent wire fields to NULL in Delta — so a DOUBLE tag with `numeric_value=64.22` but `boolean_value=false` would show `boolean_value` as NULL, not false. A legitimate `numeric_value=0.0` reading would also be NULL.

The `optional` keyword (protobuf 3.15+) adds field-presence tracking. Once `setX()` is called, the field is always serialized — even at the default value. This ensures Zerobus writes the actual value to Delta, not NULL.

## Timestamp units

- **Java (OtEventMapper):** `event_time` and `ingestion_timestamp` are set in **microseconds** (`System.currentTimeMillis() * 1000L`, `event.getTimestamp().getTime() * 1000L`).
- **Delta table:** `event_time` and `ingestion_timestamp` are **BIGINT** storing **microseconds** since epoch.
- Proto comments and this doc say "microseconds"; do not change to milliseconds without updating both Java and table.

## If you change the table

After changing `examples/agl_fleet/setup_databricks.sql` or the proto:

1. Ensure column **order** matches the proto field order above.
2. Ensure **names** match (snake_case).
3. Ensure **types**: int64→BIGINT, int32→INT, double→DOUBLE, bool→BOOLEAN, string→STRING.
4. Re-run `make db-setup-sql` (or apply DDL) and `make configure-83` so the gateway points at the table.

Zerobus docs recommend generating the proto **from** the table (`python -m zerobus.tools.generate_proto` or Java SDK tool). This repo uses a hand-written proto; keep it in sync with the table manually.

## Liquid clustering incompatibility (CLUSTER BY causes 1521)

**Zerobus Ingest does NOT support tables with liquid clustering (`CLUSTER BY`).** Stream creation fails with `INTERNAL: Error Code 1521` if the target table has any `CLUSTER BY` clause.

This was systematically isolated (2026-02-14) by testing 6 table variants:

| Constraint | Result |
|---|---|
| None (bare columns) | PASS |
| NOT NULL | PASS |
| PRIMARY KEY | PASS |
| **CLUSTER BY** | **FAIL (1521)** |
| CDF | PASS |
| All combined | **FAIL** (due to CLUSTER BY) |

**Workaround:** Do not use `CLUSTER BY` on tables that Zerobus writes to. If you need clustering for query performance, pause Zerobus ingest, add clustering (`ALTER TABLE ... CLUSTER BY (event_time, tag_path)`), OPTIMIZE, then remove it (`ALTER TABLE ... CLUSTER BY NONE`) before resuming Zerobus.

## Generated columns not supported (GENERATED ALWAYS AS causes 1015)

**Zerobus Ingest does NOT support tables with generated columns.** Stream creation fails with `UNIMPLEMENTED: Feature 'generatedColumns' is not supported. Error Code: 1015` if the target table has any `GENERATED ALWAYS AS` column.

This means the common OT/IoT pattern of partitioning by a computed date column does **not** work with Zerobus:

```sql
-- This WILL NOT work with Zerobus:
CREATE TABLE raw_tags (
  event_time BIGINT,
  event_day  DATE GENERATED ALWAYS AS (CAST(FROM_UNIXTIME(event_time / 1000000) AS DATE)),
  ...
) PARTITIONED BY (event_day)
```

## Traditional partitioning works (PARTITIONED BY)

**Zerobus Ingest DOES support traditional Delta partitioning** (`PARTITIONED BY`) on regular (non-generated) columns. Tested and confirmed (2026-02-14):

| Variant | Result |
|---|---|
| `PARTITIONED BY (tag_provider)` — existing STRING column | **PASS** |
| `PARTITIONED BY (event_day)` — regular DATE column, writer provides epoch-days int | **PASS** |
| `PARTITIONED BY (event_day)` — regular INT column, writer provides epoch-days int | **PASS** |
| `PARTITIONED BY (event_day)` — DATE column, writer provides string "2026-02-14" | **FAIL (4044)** — Zerobus expects dates as epoch-days integers |

**Key finding:** DATE columns work with Zerobus but the JSON value **must be an integer** (epoch days since 1970-01-01), not a string like `"2026-02-14"`. Sending a string causes Error 4044 "invalid digit found in string".

### Should you partition the Zerobus landing table?

**Probably not.** The `raw_tags` table is a bronze landing zone optimized for write throughput. Delta data skipping on `event_time BIGINT` already provides file pruning for time-range queries without partitioning. The silver/gold tables downstream (written by Spark, not Zerobus) can freely use `CLUSTER BY` for read performance.

Adding partitioning to the landing table requires changing the protobuf, Java mapper, and every deployment — significant churn for marginal benefit. Liquid clustering support for Zerobus is also likely coming, which would be the right solution.

See `onboarding/ZEROBUS_CLUSTER_BY_BUG.md` for the full analysis and recommendation.
