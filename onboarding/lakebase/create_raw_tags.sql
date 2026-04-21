-- Lakebase (Databricks PostgreSQL) raw_tags table
-- Mirror of the Delta raw_tags schema for dual-sink support

CREATE TABLE IF NOT EXISTS raw_tags (
    event_id TEXT PRIMARY KEY,
    event_time BIGINT NOT NULL,
    tag_path TEXT NOT NULL,
    tag_provider TEXT,
    numeric_value DOUBLE PRECISION,
    string_value TEXT,
    boolean_value BOOLEAN,
    quality TEXT,
    quality_code INTEGER,
    source_system TEXT,
    ingestion_timestamp BIGINT NOT NULL,
    data_type TEXT,
    alarm_state TEXT,
    alarm_priority INTEGER,
    sdt_compressed BOOLEAN,
    compression_ratio DOUBLE PRECISION,
    sdt_enabled BOOLEAN,
    batch_bytes_sent BIGINT
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_raw_tags_event_time ON raw_tags (event_time DESC);
CREATE INDEX IF NOT EXISTS idx_raw_tags_tag_path ON raw_tags (tag_path);
CREATE INDEX IF NOT EXISTS idx_raw_tags_ingestion_timestamp ON raw_tags (ingestion_timestamp DESC);
