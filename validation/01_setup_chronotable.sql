-- Validation setup: a LakeTS ChronoTable target for the connector's DIRECT sink
-- (no raw_tags adapter, no routing trigger). Proves the rewritten INSERT the
-- connector now emits (timestampMode=TIMESTAMPTZ, conflict=(event_time,event_id))
-- lands correctly. Isolated in schema ign_val so it never touches the demo.

CREATE SCHEMA IF NOT EXISTS ign_val;

DROP TABLE IF EXISTS ign_val.ignition_tag_events CASCADE;

-- Same 18 columns as the connector's OTEvent, but the two time columns are
-- TIMESTAMPTZ (LakeTS partition key must be a real timestamp) + db_received_at.
CREATE TABLE ign_val.ignition_tag_events (
    event_id            TEXT        NOT NULL,
    event_time          TIMESTAMPTZ NOT NULL,
    tag_path            TEXT        NOT NULL,
    tag_provider        TEXT        NOT NULL,
    numeric_value       DOUBLE PRECISION,
    string_value        TEXT,
    boolean_value       BOOLEAN,
    quality             TEXT,
    quality_code        INTEGER,
    source_system       TEXT        NOT NULL,
    ingestion_timestamp TIMESTAMPTZ NOT NULL,
    data_type           TEXT,
    alarm_state         TEXT,
    alarm_priority      INTEGER,
    sdt_compressed      BOOLEAN,
    compression_ratio   DOUBLE PRECISION,
    sdt_enabled         BOOLEAN,
    batch_bytes_sent    BIGINT,
    db_received_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

SELECT lakets.create_chronotable('ignition_tag_events', 'event_time', '1 day',
                                 p_schema_name => 'ign_val', p_if_not_exists => TRUE);

-- The composite unique the connector's ON CONFLICT (event_time, event_id) targets.
ALTER TABLE ign_val.ignition_tag_events
    DROP CONSTRAINT IF EXISTS uq_ite_event,
    ADD CONSTRAINT uq_ite_event UNIQUE (event_time, event_id);

-- LVC + 1-minute rollup, same as the customer setup would use.
SELECT lakets.enable_lvc('ignition_tag_events', ARRAY['tag_path'],
    ARRAY['numeric_value','string_value','boolean_value','quality','data_type','event_time'],
    p_schema_name => 'ign_val');
