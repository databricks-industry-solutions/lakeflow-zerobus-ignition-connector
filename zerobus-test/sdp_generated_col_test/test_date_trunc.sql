-- Test B: Compute event_day in the SELECT (standard SDP pattern).
-- Result: PASS (100 rows) -- just a regular column transformation, no special Delta feature.

CREATE OR REFRESH STREAMING TABLE test_date_trunc
CLUSTER BY (event_day, tag_path)
AS SELECT
  event_id,
  event_time,
  tag_path,
  tag_provider,
  numeric_value,
  quality,
  source_system,
  DATE(FROM_UNIXTIME(event_time / 1000000))                      AS event_day,
  DATE_TRUNC('HOUR', FROM_UNIXTIME(event_time / 1000000))        AS event_hour,
  DATE_TRUNC('MINUTE', FROM_UNIXTIME(event_time / 1000000))      AS event_minute
FROM STREAM(agl_demo.ot.raw_tags)
LIMIT 100;
