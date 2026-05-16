-- Lakebase/PostgreSQL target table schema for sinkMode=lakebase
-- Replace schema/table name as needed.

CREATE TABLE IF NOT EXISTS raw_tags (
  event_id TEXT PRIMARY KEY,
  event_time BIGINT NOT NULL,
  tag_path TEXT NOT NULL,
  tag_provider TEXT NOT NULL,
  numeric_value DOUBLE PRECISION,
  string_value TEXT,
  boolean_value BOOLEAN,
  quality TEXT,
  quality_code INTEGER,
  source_system TEXT NOT NULL,
  ingestion_timestamp BIGINT NOT NULL,
  data_type TEXT,
  alarm_state TEXT,
  alarm_priority INTEGER,
  sdt_compressed BOOLEAN,
  compression_ratio DOUBLE PRECISION,
  sdt_enabled BOOLEAN,
  batch_bytes_sent BIGINT
);

CREATE INDEX IF NOT EXISTS idx_raw_tags_event_time ON raw_tags (event_time DESC);
CREATE INDEX IF NOT EXISTS idx_raw_tags_source_system ON raw_tags (source_system);
CREATE INDEX IF NOT EXISTS idx_raw_tags_tag_path ON raw_tags (tag_path);
