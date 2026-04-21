-- Diagnose: raw_tags is populated but the AGL OT Lakehouse app dashboard shows nothing
-- Run in Databricks SQL Warehouse (same workspace as the app). Uses agl_demo.ot by default;
-- replace with your APP_TARGET_CATALOG and APP_TARGET_SCHEMA if different.
--
-- The dashboard shows metrics only for events in the last 5–10 minutes (event_time).
-- If all rows are older than that, or the app is querying a different catalog/schema, you see empty KPIs.

-- 1. Table the app reads from (must match Zerobus target and app env APP_TARGET_CATALOG / APP_TARGET_SCHEMA)
SELECT 'raw_tags' AS table_name, COUNT(*) AS total_rows
FROM agl_demo.ot.raw_tags;

-- 2. Time range of data vs "now" (dashboard filter: event_time in last 10 minutes)
SELECT
  COUNT(*) AS total_rows,
  COUNT(*) FILTER (WHERE TIMESTAMP_MICROS(event_time) >= TIMESTAMPADD(MINUTE, -10, CURRENT_TIMESTAMP())) AS rows_in_last_10_min,
  CURRENT_TIMESTAMP() AS warehouse_now,
  MIN(TIMESTAMP_MICROS(event_time)) AS oldest_event_time,
  MAX(TIMESTAMP_MICROS(event_time)) AS newest_event_time
FROM agl_demo.ot.raw_tags;

-- If rows_in_last_10_min = 0 but total_rows > 0: data is older than 10 minutes.
--   Fix: Run the simulator (make simulate-83) so new events land, or check clock on Ignition gateway.
-- If warehouse_now is very different from newest_event_time: timezone or clock skew.

-- 3. Sample recent rows (confirm schema and event_time scale)
SELECT event_time, ingestion_timestamp, tag_path, tag_provider
FROM agl_demo.ot.raw_tags
ORDER BY event_time DESC
LIMIT 5;
