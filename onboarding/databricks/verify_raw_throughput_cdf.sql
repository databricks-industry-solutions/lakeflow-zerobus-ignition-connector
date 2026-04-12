-- Verify and fix: raw_throughput not updating (CDF on raw_tags)
-- Run in Databricks SQL Warehouse or a notebook. Uses catalog/schema agl_demo.ot by default.
--
-- raw_throughput is populated by the SDP pipeline reading the change data feed from raw_tags.
-- If raw_tags has data but raw_throughput does not, CDF may be disabled on raw_tags.

-- 1. Check if CDF is enabled on raw_tags
SHOW TBLPROPERTIES agl_demo.ot.raw_tags ('delta.enableChangeDataFeed');
-- Expected: delta.enableChangeDataFeed = true

-- 2. If the above shows false or the property is missing, enable CDF (run this once)
ALTER TABLE agl_demo.ot.raw_tags SET TBLPROPERTIES (delta.enableChangeDataFeed = 'true');

-- 3. Confirm
SHOW TBLPROPERTIES agl_demo.ot.raw_tags ('delta.enableChangeDataFeed');

-- 4. Optional: quick row counts (raw_tags should have rows; raw_throughput will fill after pipeline consumes CDF)
-- SELECT 'raw_tags' AS tbl, COUNT(*) AS n FROM agl_demo.ot.raw_tags
-- UNION ALL
-- SELECT 'raw_throughput', COUNT(*) FROM agl_demo.ot.raw_throughput;
