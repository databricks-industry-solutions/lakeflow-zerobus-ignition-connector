-- =============================================================================
-- Ignition -> LakeTS DIRECT-SINK target (no adapter table, no routing trigger).
-- For use with the patched connector (branch lakets-chronotable-sink):
--   postgresTimestampMode=TIMESTAMPTZ, postgresConflictColumns="event_time, event_id",
--   postgresNullUnusedValueColumns=true, postgresTable="ignition_tag_events".
--
-- Run AFTER installing LakeTS core (lakets.sql) into the database:
--   databricks psql --project lakets-eval --branch main --endpoint primary \
--     --profile DEFAULT -- -d databricks_postgres -f 00_ignition_chronotable_direct.sql
-- =============================================================================

-- 1. The ChronoTable: 18 OTEvent columns, but the two time columns are TIMESTAMPTZ
--    (LakeTS partition key must be a real timestamp) + db_received_at arrival stamp.
CREATE TABLE IF NOT EXISTS ignition_tag_events (
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

-- 1-day chunks. create_chronotable rebuilds the table from column defs (preserves
-- NOT NULL + DEFAULT, so db_received_at DEFAULT now() survives); drops PK/constraints.
SELECT lakets.create_chronotable('ignition_tag_events', 'event_time', '1 day',
                                 p_if_not_exists => TRUE);

-- 2. Dedupe key the connector's ON CONFLICT (event_time, event_id) targets.
--    Must include the partition column (event_time) on a partitioned table.
ALTER TABLE ignition_tag_events
    DROP CONSTRAINT IF EXISTS uq_ite_event,
    ADD CONSTRAINT uq_ite_event UNIQUE (event_time, event_id);

-- Helpful secondary indexes (LakeTS creates the time index).
CREATE INDEX IF NOT EXISTS idx_ite_tag_path
    ON ignition_tag_events (tag_path, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_ite_source_system
    ON ignition_tag_events (source_system);

-- 3. Last-value cache -- the live HMI / current-value read path.
SELECT lakets.enable_lvc(
    'ignition_tag_events',
    ARRAY['tag_path'],
    ARRAY['numeric_value', 'string_value', 'boolean_value', 'quality',
          'data_type', 'event_time']);

-- 4. 1-minute analog rollup for trend charts (avg/min/max/last per tag per minute).
SELECT lakets.create_rollup(
    'ignition_tags_1m',
    $q$SELECT lakets.time_bucket('1 minute', event_time) AS bucket,
              tag_path,
              avg(numeric_value)   AS avg_value,
              min(numeric_value)   AS min_value,
              max(numeric_value)   AS max_value,
              lakets.last(numeric_value, event_time) AS last_value,
              count(*)             AS sample_count
         FROM ignition_tag_events
        WHERE numeric_value IS NOT NULL
        GROUP BY 1, 2$q$,
    '1 minute',
    'ignition_tag_events');

-- create_rollup does NOT auto-install the invalidation trigger; without it,
-- refresh_rollup finds no dirty buckets and the rollup never advances.
SELECT lakets.enable_rollup_invalidation('ignition_tags_1m');

-- Default refresh_lag is 1 hour, which makes refresh_rollup a no-op for a
-- 1-minute rollup. No setter fn; update the registry directly.
UPDATE lakets._rollup_registry SET refresh_lag = '1 minute'
 WHERE name = 'ignition_tags_1m';

-- 5. Covering index on the rollup table for fast per-tag trend reads
--    (Index Only Scan instead of a Seq Scan led by bucket).
CREATE INDEX IF NOT EXISTS idx_rollup_ignition_tags_1m_tag_bucket
    ON _rollup_ignition_tags_1m (tag_path, bucket)
    INCLUDE (avg_value, min_value, max_value, last_value, sample_count);

-- 6. Lifecycle: sync shadow + tiering + retention. Retention is fail-closed on
--    CDF, so nothing is dropped until CDF is enabled on the lakets_cdf schema
--    (a manual Databricks UI step) and the sync confirms a durable UC copy.
SELECT lakets.enable_sync('ignition_tag_events');       -- WARNING about CDF-not-enabled is expected
SELECT lakets.add_tiering_policy('ignition_tag_events', '7 days');
SELECT lakets.add_retention_policy('ignition_tag_events', '90 days');

-- Sanity read-backs.
SELECT 'chronotable' AS obj, count(*) AS n FROM lakets._chronotable_registry WHERE table_name='ignition_tag_events'
UNION ALL SELECT 'rollup', count(*) FROM lakets._rollup_registry WHERE name LIKE 'ignition%'
UNION ALL SELECT 'lvc', count(*) FROM lakets._lvc_registry lr JOIN lakets._chronotable_registry ct ON ct.id=lr.chronotable_id WHERE ct.table_name='ignition_tag_events';
