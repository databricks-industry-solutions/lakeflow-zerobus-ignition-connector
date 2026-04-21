-- Test C: Materialized view with time-truncated columns and clustering.
-- Result: PASS (216 rows) -- standard gold-layer time-bucketed aggregation pattern.

CREATE OR REFRESH MATERIALIZED VIEW test_mv_daily
CLUSTER BY (event_day, tag_path)
AS SELECT
  DATE(FROM_UNIXTIME(event_time / 1000000))  AS event_day,
  tag_path,
  source_system,
  COUNT(*)                                    AS event_count,
  AVG(numeric_value)                          AS avg_value,
  MIN(numeric_value)                          AS min_value,
  MAX(numeric_value)                          AS max_value
FROM agl_demo.ot.raw_tags
GROUP BY 1, 2, 3;
