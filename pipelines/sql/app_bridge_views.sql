-- Bridge views: Map Zerobus connector output to the demo app's expected schema.
-- The connector writes to __CATALOG__.__SCHEMA__.raw_tags with its native schema (bigint timestamps,
-- tag_path, tag_provider, etc). The app expects a different schema (TIMESTAMP columns,
-- asset_id, tag_name, tag_value, etc).
--
-- Solution: Create views in __CATALOG__.app that transform the connector output.
-- Then set app.yaml DATABRICKS_SCHEMA=app (instead of ot).
--
-- Asset metadata now lives in __CATALOG__.__SCHEMA__.asset_hierarchy (single source of truth).
-- See pipelines/sql/setup_asset_framework.sql for DDL and seed data.

-- 0. Create the app schema
CREATE SCHEMA IF NOT EXISTS __CATALOG__.app;

-- 1. Bridge view: raw_tags
-- Maps connector output -> app expected schema
-- Tag path structure: [provider]AGL/Australia/NSW/{Site}/Site01/{Asset}/{Subsystem}/{Signal}
-- For site-level tags: [provider]AGL/Australia/NSW/{Site}/Site01/{Subsystem}/{Signal}
CREATE OR REPLACE VIEW __CATALOG__.app.raw_tags AS
WITH parsed AS (
  SELECT
    event_time,
    ingestion_timestamp,
    tag_path,
    tag_provider,
    numeric_value,
    string_value,
    boolean_value,
    quality,
    quality_code,
    source_system,
    data_type,
    SPLIT(REGEXP_REPLACE(tag_path, '^\[.*?\]', ''), '/') AS parts
  FROM __CATALOG__.__SCHEMA__.raw_tags
)
SELECT
  TIMESTAMP_MICROS(event_time) AS event_timestamp,
  TIMESTAMP_MICROS(ingestion_timestamp) AS ingest_timestamp,
  LOWER(CONCAT(parts[3], '_', parts[5])) AS asset_id,
  CASE
    WHEN tag_provider = 'agl_bess' THEN 'battery_bess'
    WHEN tag_provider = 'agl_grid' THEN 'grid_infrastructure'
    WHEN tag_provider = 'agl_market' THEN 'market_data'
    WHEN tag_provider = 'agl_cmms' THEN 'maintenance'
    ELSE tag_provider
  END AS asset_type,
  LOWER(ARRAY_JOIN(SLICE(parts, 7, SIZE(parts) - 6), '/')) AS tag_name,
  COALESCE(
    numeric_value,
    CASE WHEN boolean_value = true THEN 1.0 WHEN boolean_value = false THEN 0.0 ELSE NULL END
  ) AS tag_value,
  quality_code AS quality,
  source_system,
  false AS sdt_compressed,
  CAST(NULL AS DOUBLE) AS compression_ratio
FROM parsed
WHERE SIZE(parts) >= 6;

-- 2. Ingest metrics view (5-second windows aggregated from raw events)
CREATE OR REPLACE VIEW __CATALOG__.app.ingest_metrics AS
SELECT
  TIMESTAMP_MICROS(CAST(FLOOR(event_time / 5000000) * 5000000 AS BIGINT)) AS window_start,
  TIMESTAMP_MICROS(CAST(FLOOR(event_time / 5000000) * 5000000 + 5000000 AS BIGINT)) AS window_end,
  COUNT(*) AS records_raw,
  COUNT(*) AS records_after_sdt,
  COUNT(*) * 100 AS bytes_estimate,
  AVG(CAST(ingestion_timestamp - event_time AS DOUBLE) / 1000.0) AS avg_latency_ms,
  PERCENTILE_APPROX(CAST(ingestion_timestamp - event_time AS DOUBLE) / 1000.0, 0.99) AS p99_latency_ms,
  COUNT(DISTINCT tag_path) AS tags_active,
  1.0 AS sdt_compression_ratio
FROM __CATALOG__.__SCHEMA__.raw_tags
GROUP BY 1, 2;

-- 3. SDT config - reference the existing ot.sdt_config table (read-only view).
--    The app backend must use APP_TARGET_SCHEMA=__SCHEMA__ (ot) so MERGE targets the table;
--    MERGE into a view is not supported.
CREATE OR REPLACE VIEW __CATALOG__.app.sdt_config AS
SELECT * FROM __CATALOG__.__SCHEMA__.sdt_config;
