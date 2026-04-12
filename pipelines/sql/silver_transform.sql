-- Silver aggregation transform
-- Aggregates raw_tags into windowed summaries in aggregated_tags.
-- Run as a scheduled Databricks SQL query or Workflow task.
-- Idempotent: uses MERGE to avoid duplicate inserts on re-run.
-- Replace ${catalog} and ${schema} before execution.

-- 1-minute windows
MERGE INTO ${catalog}.${schema}.aggregated_tags AS target
USING (
  SELECT
    window.start                          AS window_start,
    window.end                            AS window_end,
    asset_id,
    tag_name,
    AVG(tag_value)                        AS avg_value,
    MIN(tag_value)                        AS min_value,
    MAX(tag_value)                        AS max_value,
    STDDEV(tag_value)                     AS stddev_value,
    COUNT(*)                              AS sample_count,
    SUM(CASE WHEN sdt_compressed THEN 1 ELSE 0 END) AS compressed_count
  FROM ${catalog}.${schema}.raw_tags
  WHERE event_timestamp >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTES
  GROUP BY
    window(event_timestamp, '1 minute'),
    asset_id,
    tag_name
) AS source
ON target.window_start = source.window_start
  AND target.window_end = source.window_end
  AND target.asset_id = source.asset_id
  AND target.tag_name = source.tag_name
WHEN NOT MATCHED THEN INSERT *;

-- 5-minute windows
MERGE INTO ${catalog}.${schema}.aggregated_tags AS target
USING (
  SELECT
    window.start                          AS window_start,
    window.end                            AS window_end,
    asset_id,
    tag_name,
    AVG(tag_value)                        AS avg_value,
    MIN(tag_value)                        AS min_value,
    MAX(tag_value)                        AS max_value,
    STDDEV(tag_value)                     AS stddev_value,
    COUNT(*)                              AS sample_count,
    SUM(CASE WHEN sdt_compressed THEN 1 ELSE 0 END) AS compressed_count
  FROM ${catalog}.${schema}.raw_tags
  WHERE event_timestamp >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTES
  GROUP BY
    window(event_timestamp, '5 minutes'),
    asset_id,
    tag_name
) AS source
ON target.window_start = source.window_start
  AND target.window_end = source.window_end
  AND target.asset_id = source.asset_id
  AND target.tag_name = source.tag_name
WHEN NOT MATCHED THEN INSERT *;

-- 15-minute windows
MERGE INTO ${catalog}.${schema}.aggregated_tags AS target
USING (
  SELECT
    window.start                          AS window_start,
    window.end                            AS window_end,
    asset_id,
    tag_name,
    AVG(tag_value)                        AS avg_value,
    MIN(tag_value)                        AS min_value,
    MAX(tag_value)                        AS max_value,
    STDDEV(tag_value)                     AS stddev_value,
    COUNT(*)                              AS sample_count,
    SUM(CASE WHEN sdt_compressed THEN 1 ELSE 0 END) AS compressed_count
  FROM ${catalog}.${schema}.raw_tags
  WHERE event_timestamp >= CURRENT_TIMESTAMP() - INTERVAL 120 MINUTES
  GROUP BY
    window(event_timestamp, '15 minutes'),
    asset_id,
    tag_name
) AS source
ON target.window_start = source.window_start
  AND target.window_end = source.window_end
  AND target.asset_id = source.asset_id
  AND target.tag_name = source.tag_name
WHEN NOT MATCHED THEN INSERT *;

-- 1-hour windows
MERGE INTO ${catalog}.${schema}.aggregated_tags AS target
USING (
  SELECT
    window.start                          AS window_start,
    window.end                            AS window_end,
    asset_id,
    tag_name,
    AVG(tag_value)                        AS avg_value,
    MIN(tag_value)                        AS min_value,
    MAX(tag_value)                        AS max_value,
    STDDEV(tag_value)                     AS stddev_value,
    COUNT(*)                              AS sample_count,
    SUM(CASE WHEN sdt_compressed THEN 1 ELSE 0 END) AS compressed_count
  FROM ${catalog}.${schema}.raw_tags
  WHERE event_timestamp >= CURRENT_TIMESTAMP() - INTERVAL 240 MINUTES
  GROUP BY
    window(event_timestamp, '1 hour'),
    asset_id,
    tag_name
) AS source
ON target.window_start = source.window_start
  AND target.window_end = source.window_end
  AND target.asset_id = source.asset_id
  AND target.tag_name = source.tag_name
WHEN NOT MATCHED THEN INSERT *;
