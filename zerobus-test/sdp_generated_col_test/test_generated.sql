-- Test A: Can SDP streaming tables use GENERATED ALWAYS AS?
-- Result: PASS (100 rows) -- SDP uses Spark's Delta writer which supports generated columns.

CREATE OR REFRESH STREAMING TABLE test_generated (
  event_id              STRING,
  event_time            BIGINT,
  tag_path              STRING,
  event_day             DATE GENERATED ALWAYS AS (CAST(FROM_UNIXTIME(event_time / 1000000) AS DATE))
)
AS SELECT
  event_id,
  event_time,
  tag_path
FROM STREAM(agl_demo.ot.raw_tags)
LIMIT 100;
