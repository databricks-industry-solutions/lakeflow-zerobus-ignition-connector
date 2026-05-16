-- Zerobus target table schema (Delta / Unity Catalog)
-- Update catalog/schema/table names as needed.

CREATE TABLE IF NOT EXISTS agl_ignition.scada_data.tag_events (
  event_id STRING NOT NULL,
  event_time TIMESTAMP,
  tag_path STRING,
  tag_provider STRING,
  numeric_value DOUBLE,
  string_value STRING,
  boolean_value BOOLEAN,
  quality STRING,
  quality_code INT,
  source_system STRING,
  ingestion_timestamp BIGINT,
  data_type STRING,
  alarm_state STRING,
  alarm_priority INT,
  sdt_compressed BOOLEAN,
  compression_ratio DOUBLE,
  sdt_enabled BOOLEAN,
  batch_bytes_sent BIGINT
)
USING DELTA;
