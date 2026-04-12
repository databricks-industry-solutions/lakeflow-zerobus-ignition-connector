-- Silver scaffolding (tables + base view)
-- Catalog: agl_ignition
-- Bronze:  agl_ignition.scada_data.tag_events
-- Silver:  agl_ignition.ot

CREATE CATALOG IF NOT EXISTS agl_ignition;
CREATE SCHEMA IF NOT EXISTS agl_ignition.scada_data;
CREATE SCHEMA IF NOT EXISTS agl_ignition.ot;

-- Dimensions (assets + mapping)
CREATE TABLE IF NOT EXISTS agl_ignition.ot.silver_asset_registry (
  asset_id STRING,
  parent_asset_id STRING,
  asset_type STRING,
  site STRING,
  display_name STRING,
  active BOOLEAN
)
USING DELTA;

CREATE TABLE IF NOT EXISTS agl_ignition.ot.silver_signal_mapping (
  tag_path STRING,
  asset_id STRING,
  signal_name STRING,
  unit STRING,
  scale DOUBLE,
  offset DOUBLE,
  source_domain STRING, -- bess|grid|market|cmms
  active BOOLEAN
)
USING DELTA;

-- Normalized long-form view
CREATE OR REPLACE VIEW agl_ignition.ot.silver_events_normalized AS
SELECT
  b.event_time,
  b.ingestion_timestamp,
  b.source_system,
  b.tag_provider,
  m.source_domain,
  m.asset_id,
  m.signal_name,
  m.unit,
  CASE
    WHEN b.numeric_value IS NOT NULL THEN (b.numeric_value * COALESCE(m.scale, 1.0) + COALESCE(m.offset, 0.0))
    WHEN b.boolean_value IS NOT NULL THEN CAST(b.boolean_value AS DOUBLE)
    ELSE NULL
  END AS value_numeric,
  b.string_value,
  b.boolean_value,
  b.quality,
  b.quality_code,
  b.tag_path
FROM agl_ignition.scada_data.tag_events b
LEFT JOIN agl_ignition.ot.silver_signal_mapping m
  ON b.tag_path = m.tag_path AND m.active = true;

