# OTEvent protobuf and Delta schema alignment

The connector sends `OTEvent` protobuf messages in Zerobus mode. The target Delta table (commonly `raw_tags`) must stay aligned with the protobuf schema in names, order, and types.

## Field alignment

| Proto (`ot_event.proto`) | Delta column | Notes |
|---|---|---|
| `event_id` (`string`) | `event_id` (`STRING`) | unique event key |
| `event_time` (`int64`) | `event_time` (`BIGINT`) | microseconds since Unix epoch |
| `tag_path` (`string`) | `tag_path` (`STRING`) | full tag path |
| `tag_provider` (`string`) | `tag_provider` (`STRING`) | Ignition provider |
| `numeric_value` (`optional double`) | `numeric_value` (`DOUBLE`) | nullable |
| `string_value` (`optional string`) | `string_value` (`STRING`) | nullable |
| `boolean_value` (`optional bool`) | `boolean_value` (`BOOLEAN`) | nullable |
| `quality` (`optional string`) | `quality` (`STRING`) | nullable |
| `quality_code` (`optional int32`) | `quality_code` (`INT`) | nullable |
| `source_system` (`string`) | `source_system` (`STRING`) | source id |
| `ingestion_timestamp` (`int64`) | `ingestion_timestamp` (`BIGINT`) | microseconds since Unix epoch |
| `data_type` (`string`) | `data_type` (`STRING`) | source datatype |
| `alarm_state` (`optional string`) | `alarm_state` (`STRING`) | nullable |
| `alarm_priority` (`optional int32`) | `alarm_priority` (`INT`) | nullable |
| `sdt_compressed` (`optional bool`) | `sdt_compressed` (`BOOLEAN`) | nullable |
| `compression_ratio` (`optional double`) | `compression_ratio` (`DOUBLE`) | nullable |
| `sdt_enabled` (`optional bool`) | `sdt_enabled` (`BOOLEAN`) | nullable |
| `batch_bytes_sent` (`optional int64`) | `batch_bytes_sent` (`BIGINT`) | nullable |

## Why optional fields matter

Proto3 does not serialize default values unless field presence is tracked. Using `optional` preserves explicit values like `0`, `0.0`, `false`, and empty strings, which avoids unintended NULLs in Delta.

## Timestamp units

- The Java mapper writes `event_time` and `ingestion_timestamp` in microseconds.
- Delta columns must remain `BIGINT` microseconds.
- Do not change units to milliseconds unless code and schema are both changed together.

## If you change schema or proto

1. Keep column order and names aligned with proto field order.
2. Keep type mapping aligned (`int64` -> `BIGINT`, `int32` -> `INT`, `double` -> `DOUBLE`, `bool` -> `BOOLEAN`, `string` -> `STRING`).
3. Reapply table DDL and reconfigure the connector to point at the updated target table.

## Zerobus table compatibility notes

- `CLUSTER BY` on the landing table can break Zerobus stream creation (observed as error 1521).
- Generated columns (`GENERATED ALWAYS AS`) are not supported by Zerobus ingest (observed as error 1015).
- Traditional partitioning (`PARTITIONED BY`) can work when data types and encoded values match expected formats.

For stability, keep the landing table simple and apply heavier optimization patterns in downstream tables.
