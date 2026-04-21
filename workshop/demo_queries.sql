-- =============================================================================
-- Medallion Architecture Workshop: Live Demo Queries
-- =============================================================================
-- Organized by presentation section. Run these in a Databricks SQL editor
-- during the workshop. Each section header matches the slide deck.
--
-- Catalog: medallion (3 schemas: bronze, silver, gold)
-- =============================================================================


-- =============================================
-- SECTION 3: UNDER THE HOOD — Files in Azure
-- =============================================
-- Run these while showing Azure portal side-by-side

-- Where are the files? (shows the ADLS path)
DESCRIBE DETAIL medallion.bronze.raw_tags;

-- What happened to this table? (transaction history)
DESCRIBE HISTORY medallion.bronze.raw_tags LIMIT 10;

-- How many files and how big?
SELECT
  format_number(numFiles, 0)                  AS num_files,
  format_number(sizeInBytes / 1048576, 1)     AS size_mb,
  format_number(numFiles * 1.0, 0)            AS parquet_files
FROM (DESCRIBE DETAIL medallion.bronze.raw_tags);

-- Time travel: the very first version
SELECT * FROM medallion.bronze.raw_tags VERSION AS OF 0 LIMIT 5;


-- =============================================
-- SECTION 5: BRONZE — Land Everything
-- =============================================

-- How many events do we have?
SELECT format_number(COUNT(*), 0) AS total_events
FROM medallion.bronze.raw_tags;

-- Latest events — show the raw, messy data
SELECT
  event_time,
  tag_path,
  numeric_value,
  quality
FROM medallion.bronze.raw_tags
ORDER BY ingestion_timestamp DESC
LIMIT 10;

-- Point out: event_time is a meaningless BIGINT
-- Point out: tag_path is a packed string nobody can read
-- Point out: no asset_id, no signal_name, no units

-- How many distinct tag paths? (shows the variety)
SELECT
  COUNT(DISTINCT tag_path)    AS unique_tags,
  COUNT(DISTINCT tag_provider) AS unique_providers,
  MIN(to_timestamp(event_time / 1000000)) AS earliest_event,
  MAX(to_timestamp(event_time / 1000000)) AS latest_event
FROM medallion.bronze.raw_tags;

-- Show tag_path structure (pick a few examples)
SELECT DISTINCT tag_path
FROM medallion.bronze.raw_tags
WHERE tag_provider = 'agl_bess'
LIMIT 10;


-- =============================================
-- LIVE FEED: Mirror fresh data into workshop tables
-- =============================================
-- Run this periodically during the demo to show data growing.
-- (Only needed if the simulator is writing to the source tables)

-- INSERT INTO medallion.bronze.raw_tags
-- SELECT event_id, event_time, tag_path, tag_provider,
--        numeric_value, string_value, boolean_value,
--        quality, quality_code, source_system, ingestion_timestamp,
--        data_type, sdt_compressed, compression_ratio
-- FROM ot_demo.ot.raw_tags
-- WHERE ingestion_timestamp > unix_micros(current_timestamp() - INTERVAL 30 SECONDS)
--   AND event_id NOT IN (SELECT event_id FROM medallion.bronze.raw_tags);


-- =============================================
-- SECTION 6: SILVER — Clean & Enrich
-- =============================================

-- STEP 1: Parse — compare bronze vs silver.parsed_tags
-- Bronze (raw):
SELECT event_time, tag_path, numeric_value
FROM medallion.bronze.raw_tags
ORDER BY ingestion_timestamp DESC LIMIT 5;

-- Silver (parsed): same data, now with asset_id and tag_name
SELECT event_timestamp, asset_id, asset_type, tag_name, tag_value
FROM medallion.silver.parsed_tags
ORDER BY event_timestamp DESC LIMIT 5;

-- "See? The packed tag_path is now asset_id + tag_name.
--  The BIGINT timestamp is now a readable TIMESTAMP."


-- STEP 2: Aggregate — show the volume reduction
SELECT
  'bronze.raw_tags'       AS layer,
  format_number(COUNT(*), 0)       AS row_count
FROM medallion.bronze.raw_tags
UNION ALL
SELECT
  'silver.aggregated_tags',
  format_number(COUNT(*), 0)
FROM medallion.silver.aggregated_tags;

-- "From X hundred thousand rows to Y thousand. 99% reduction."

-- Show what aggregation looks like
SELECT
  window_start,
  asset_id,
  tag_name,
  ROUND(avg_value, 2)    AS avg_value,
  ROUND(min_value, 2)    AS min_value,
  ROUND(max_value, 2)    AS max_value,
  ROUND(stddev_value, 4) AS stddev,
  sample_count
FROM medallion.silver.aggregated_tags
WHERE tag_name LIKE '%soc_pct%'
  AND asset_id LIKE '%bess_01%'
ORDER BY window_start DESC
LIMIT 10;

-- "One row per tag per minute. Avg, min, max, stddev, count."


-- STEP 3: Enrich — now with human-readable names
SELECT
  window_start,
  asset_id,
  tag_name,
  signal_name,
  unit,
  source_domain,
  ROUND(avg_value, 2)  AS avg_value,
  sample_count
FROM medallion.silver.enriched_tags
WHERE signal_name IS NOT NULL
ORDER BY window_start DESC
LIMIT 15;

-- "thermal/rack_temp_c → 'Rack Temperature' in °C.
--  power/soc_pct → 'State of Charge' in %.
--  Now a human can read it."


-- DATA QUALITY: Show what expectations look like
-- (Use the pipeline UI for visual metrics — these queries complement)

-- How much bad data would we catch?
SELECT
  COUNT(*)                                                       AS total_rows,
  SUM(CASE WHEN event_timestamp IS NULL THEN 1 ELSE 0 END)     AS null_timestamps,
  SUM(CASE WHEN asset_id IS NULL OR asset_id = '' THEN 1 ELSE 0 END) AS missing_asset,
  SUM(CASE WHEN tag_value IS NULL THEN 1 ELSE 0 END)           AS null_values,
  SUM(CASE WHEN event_timestamp > current_timestamp() + INTERVAL 5 MINUTES
      THEN 1 ELSE 0 END)                                        AS future_events
FROM medallion.silver.parsed_tags;


-- Row counts across all layers (the compression story)
SELECT
  'Bronze: raw_tags'        AS layer, COUNT(*) AS rows FROM medallion.bronze.raw_tags
UNION ALL
SELECT 'Silver: parsed_tags',       COUNT(*) FROM medallion.silver.parsed_tags
UNION ALL
SELECT 'Silver: aggregated_tags',   COUNT(*) FROM medallion.silver.aggregated_tags
UNION ALL
SELECT 'Silver: enriched_tags',     COUNT(*) FROM medallion.silver.enriched_tags
UNION ALL
SELECT 'Gold: health_scores',       COUNT(*) FROM medallion.gold.health_scores
UNION ALL
SELECT 'Gold: revenue_risk',        COUNT(*) FROM medallion.gold.revenue_risk
ORDER BY layer;


-- =============================================
-- SECTION 7: GOLD — Answer the Question
-- =============================================

-- Health scores: one row per asset, sorted by risk
SELECT
  asset_id,
  ROUND(health_score, 2)     AS health_score,
  primary_risk_tag,
  risk_description,
  anomaly_count,
  total_key_tags,
  ROUND(estimated_hours_to_failure, 0) AS est_hours_to_failure
FROM medallion.gold.health_scores
ORDER BY health_score ASC
LIMIT 15;

-- "Worst assets at the top. The operations team looks at this every morning."

-- Revenue at risk: dollars the CFO understands
SELECT
  asset_id,
  ROUND(health_score, 2)             AS health,
  ROUND(trip_probability, 2)         AS trip_prob,
  capacity_mw,
  forecast_price_aud_mwh             AS price,
  CONCAT('$', format_number(revenue_at_risk_aud, 0)) AS revenue_at_risk,
  recommended_action
FROM medallion.gold.revenue_risk
ORDER BY revenue_at_risk_aud DESC
LIMIT 10;

-- "During the next high-price window, these assets cost us
--  the most if they trip. Health × price × capacity = dollars."

-- Total fleet exposure
SELECT
  COUNT(DISTINCT asset_id)                         AS assets_at_risk,
  CONCAT('$', format_number(SUM(revenue_at_risk_aud), 0)) AS total_revenue_at_risk,
  ROUND(AVG(health_score), 2)                      AS avg_fleet_health
FROM medallion.gold.revenue_risk;


-- =============================================
-- AZURE PORTAL WALKTHROUGH HELPERS
-- =============================================
-- Run these to get the exact paths to navigate in Azure portal

-- All table locations in one view
SELECT 'bronze.raw_tags'       AS table_name, location FROM (DESCRIBE DETAIL medallion.bronze.raw_tags)
UNION ALL
SELECT 'silver.parsed_tags',   location FROM (DESCRIBE DETAIL medallion.silver.parsed_tags)
UNION ALL
SELECT 'silver.aggregated_tags', location FROM (DESCRIBE DETAIL medallion.silver.aggregated_tags)
UNION ALL
SELECT 'silver.enriched_tags', location FROM (DESCRIBE DETAIL medallion.silver.enriched_tags)
UNION ALL
SELECT 'gold.health_scores',   location FROM (DESCRIBE DETAIL medallion.gold.health_scores)
UNION ALL
SELECT 'gold.revenue_risk',    location FROM (DESCRIBE DETAIL medallion.gold.revenue_risk);

-- File counts per table (to compare bronze vs silver vs gold)
SELECT 'bronze.raw_tags'         AS tbl, numFiles, ROUND(sizeInBytes/1048576.0, 1) AS size_mb FROM (DESCRIBE DETAIL medallion.bronze.raw_tags)
UNION ALL
SELECT 'silver.parsed_tags',     numFiles, ROUND(sizeInBytes/1048576.0, 1) FROM (DESCRIBE DETAIL medallion.silver.parsed_tags)
UNION ALL
SELECT 'silver.aggregated_tags', numFiles, ROUND(sizeInBytes/1048576.0, 1) FROM (DESCRIBE DETAIL medallion.silver.aggregated_tags)
UNION ALL
SELECT 'silver.enriched_tags',   numFiles, ROUND(sizeInBytes/1048576.0, 1) FROM (DESCRIBE DETAIL medallion.silver.enriched_tags)
UNION ALL
SELECT 'gold.health_scores',     numFiles, ROUND(sizeInBytes/1048576.0, 1) FROM (DESCRIBE DETAIL medallion.gold.health_scores)
UNION ALL
SELECT 'gold.revenue_risk',      numFiles, ROUND(sizeInBytes/1048576.0, 1) FROM (DESCRIBE DETAIL medallion.gold.revenue_risk);


-- =============================================
-- PI AF REPLACEMENT: Silver + UC Metadata
-- =============================================
-- Show how silver enrichment + UC descriptions replace PI Asset Framework

-- PI AF element hierarchy → Silver tag_path parsing
-- Before (PI AF): Site01 > bess_01 > thermal > rack_temp_c
-- After (Silver):  asset_id = 'tomago_bess_01', tag_name = 'thermal/rack_temp_c'
SELECT DISTINCT
  asset_id,
  tag_name,
  signal_name,
  unit,
  source_domain
FROM medallion.silver.enriched_tags
WHERE asset_id LIKE '%bess_01%'
ORDER BY source_domain, tag_name
LIMIT 20;

-- "This IS your new Asset Framework. asset_id = element,
--  tag_name = attribute path, signal_name + unit = AF metadata."

-- UC metadata = PI AF attribute descriptions
DESCRIBE TABLE EXTENDED medallion.silver.enriched_tags;
-- "See the COMMENT on each column? That's discoverable metadata.
--  PI AF stores this in element templates. UC stores it as column descriptions."


-- =============================================
-- DATA PRODUCTS: Gold Tables as Products
-- =============================================
-- Show that gold tables have contracts (schema + expectations + descriptions)

-- The data contract: what does this table promise?
DESCRIBE TABLE EXTENDED medallion.gold.health_scores;
-- Point at: table comment, column comments, column types

-- Who consumes this data product?
-- Operations: "which assets need attention?"
SELECT asset_id, health_score, primary_risk_tag, risk_description
FROM medallion.gold.health_scores
ORDER BY health_score ASC
LIMIT 5;

-- Trading desk: "what's our revenue exposure?"
SELECT asset_id, revenue_at_risk_aud, recommended_action
FROM medallion.gold.revenue_risk
ORDER BY revenue_at_risk_aud DESC
LIMIT 5;

-- "Same data platform, two data products, two audiences.
--  Each has a contract (schema), quality rules (expectations), and is discoverable."


-- =============================================
-- GENIE ENABLEMENT: Making Gold Tables AI-Ready
-- =============================================
-- Show the COMMENT ON statements that enable Genie

-- Check current table description
SELECT comment FROM information_schema.tables
WHERE table_catalog = 'medallion' AND table_schema = 'gold';

-- Check column descriptions
SELECT column_name, comment
FROM information_schema.columns
WHERE table_catalog = 'medallion'
  AND table_schema = 'gold'
  AND table_name = 'health_scores'
ORDER BY ordinal_position;

-- "Genie reads these descriptions to understand your data.
--  Clean names + descriptions = natural language access.
--  An operator can now ask: 'which assets are at risk?' and get an answer."


-- =============================================
-- BONUS: Time Travel Demo
-- =============================================

-- What did bronze look like in the first version?
SELECT COUNT(*) AS rows_in_v0
FROM medallion.bronze.raw_tags VERSION AS OF 0;

-- Compare to current
SELECT COUNT(*) AS rows_now
FROM medallion.bronze.raw_tags;

-- Full history of changes
DESCRIBE HISTORY medallion.bronze.raw_tags;

-- "Every INSERT created a new version. We can query any of them.
--  This is what the _delta_log tracks — and what we saw in Azure portal."


-- =============================================
-- BONUS: Schema Comparison Across Layers
-- =============================================
-- Great for showing "what changed between layers"

-- Bronze columns
DESCRIBE TABLE medallion.bronze.raw_tags;

-- Silver columns (parsed)
DESCRIBE TABLE medallion.silver.parsed_tags;

-- Gold columns (health)
DESCRIBE TABLE medallion.gold.health_scores;

-- "Bronze: 14 columns, source schema, raw types.
--  Silver: 9 columns, business keys, proper types.
--  Gold: 8 columns, one answer per asset."
