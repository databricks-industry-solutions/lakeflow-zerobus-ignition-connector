-- Bridge view: Map Ignition connector output to PRD schema
-- This allows the demo app (demo/app/) to query data from the Ignition connector
-- as if it were in the PRD raw_tags format.
--
-- PRD schema expects: event_timestamp, ingest_timestamp, asset_id, asset_type,
--                     tag_name, tag_value, quality, source_system, sdt_compressed, compression_ratio
--
-- Connector outputs: event_time, ingestion_timestamp, tag_path, tag_provider,
--                    numeric_value, string_value, boolean_value, quality, quality_code, source_system

-- Create schema for PRD-compatible views
CREATE SCHEMA IF NOT EXISTS agl_ignition.agl_demo_compat;

-- Bridge view: raw_tags equivalent from Ignition connector data
CREATE OR REPLACE VIEW agl_ignition.agl_demo_compat.raw_tags AS
SELECT
  n.event_time AS event_timestamp,
  n.ingestion_timestamp AS ingest_timestamp,
  n.asset_id,
  CASE
    WHEN n.source_domain = 'bess' THEN 'battery_bess'
    WHEN n.source_domain = 'grid' THEN 'grid_infrastructure'
    WHEN n.source_domain = 'market' THEN 'market_data'
    WHEN n.source_domain = 'cmms' THEN 'maintenance'
    ELSE n.source_domain
  END AS asset_type,
  n.signal_name AS tag_name,
  COALESCE(n.value_numeric,
           CASE WHEN n.boolean_value THEN 1.0 ELSE 0.0 END) AS tag_value,
  n.quality_code AS quality,
  n.source_system,
  false AS sdt_compressed,  -- Connector handles compression internally
  NULL AS compression_ratio
FROM agl_ignition.ot.silver_events_normalized n
WHERE n.asset_id IS NOT NULL;

-- Bridge view: assets equivalent from asset registry
CREATE OR REPLACE VIEW agl_ignition.agl_demo_compat.assets AS
SELECT
  asset_id,
  display_name AS asset_name,
  CASE
    WHEN asset_type = 'BESS' THEN 'battery_bess'
    WHEN asset_type = 'SUBSTATION' THEN 'grid_infrastructure'
    WHEN asset_type = 'MARKET' THEN 'market_data'
    WHEN asset_type = 'CMMS' THEN 'maintenance'
    WHEN asset_type = 'SITE' THEN 'site'
    ELSE LOWER(asset_type)
  END AS asset_type,
  site AS site_name,
  CASE
    WHEN asset_id = 'bess01' THEN 500.0
    ELSE NULL
  END AS capacity_mw,
  CASE WHEN site = 'Tomago' THEN -32.79 ELSE NULL END AS latitude,
  CASE WHEN site = 'Tomago' THEN 151.86 ELSE NULL END AS longitude,
  NULL AS commissioned_date,
  (SELECT COUNT(DISTINCT signal_name)
   FROM agl_ignition.ot.silver_signal_mapping m
   WHERE m.asset_id = r.asset_id) AS tag_count
FROM agl_ignition.ot.silver_asset_registry r
WHERE active = true;

-- Bridge view: ingest_metrics equivalent (aggregated from events)
CREATE OR REPLACE VIEW agl_ignition.agl_demo_compat.ingest_metrics AS
SELECT
  window.start AS window_start,
  window.end AS window_end,
  COUNT(*) AS records_raw,
  COUNT(*) AS records_after_sdt,  -- No SDT tracking in this path
  COUNT(*) * 100 AS bytes_estimate,  -- Rough estimate
  AVG(TIMESTAMPDIFF(MILLISECOND, event_time, ingestion_timestamp)) AS avg_latency_ms,
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY TIMESTAMPDIFF(MILLISECOND, event_time, ingestion_timestamp)) AS p99_latency_ms,
  COUNT(DISTINCT CONCAT(asset_id, '.', signal_name)) AS tags_active,
  1.0 AS sdt_compression_ratio
FROM agl_ignition.ot.silver_events_normalized
GROUP BY window(event_time, '5 seconds');

-- Usage note:
-- To use these views with the demo app, update the app's query service to reference
-- agl_ignition.agl_demo_compat.* instead of agl_demo.ot.*
-- Or create synonyms/aliases in your catalog.

-- Example: Create alias in agl_demo catalog (if needed)
-- CREATE OR REPLACE VIEW agl_demo.ot.raw_tags AS SELECT * FROM agl_ignition.agl_demo_compat.raw_tags;
