-- Fire the EXACT INSERT the patched connector emits in LakeTS profile:
--   timestampMode=TIMESTAMPTZ  -> to_timestamp(?/1000000.0) on the 2 time cols
--   conflictColumns=event_time,event_id
--   nullUnusedValueColumns=true -> boolean tag carries NULL numeric_value
-- Binds are epoch-MICROSECONDS (what OtEventMapper produces: millis*1000).
-- We simulate three JDBC binds via literal epoch-micros values.

\set ON_ERROR_STOP on

-- Row 1: a numeric (DOUBLE) tag. event_time = now (micros).
INSERT INTO ign_val.ignition_tag_events (
    event_id, event_time, tag_path, tag_provider, numeric_value, string_value,
    boolean_value, quality, quality_code, source_system, ingestion_timestamp,
    data_type, alarm_state, alarm_priority, sdt_compressed, compression_ratio,
    sdt_enabled, batch_bytes_sent)
VALUES (
    'evt-num-1', to_timestamp((extract(epoch from now())*1000000)::bigint/1000000.0),
    '[default]Line1/Temperature', 'default',
    73.4, NULL, NULL, 'GOOD', 192, 'ignition-gateway',
    to_timestamp((extract(epoch from now())*1000000)::bigint/1000000.0),
    'DOUBLE', NULL, NULL, false, NULL, false, NULL)
ON CONFLICT (event_time, event_id) DO NOTHING;

-- Row 2: a BOOLEAN tag. With null-coercion, numeric_value is bound NULL (not 0.0).
INSERT INTO ign_val.ignition_tag_events (
    event_id, event_time, tag_path, tag_provider, numeric_value, string_value,
    boolean_value, quality, quality_code, source_system, ingestion_timestamp,
    data_type, alarm_state, alarm_priority, sdt_compressed, compression_ratio,
    sdt_enabled, batch_bytes_sent)
VALUES (
    'evt-bool-1', to_timestamp((extract(epoch from now())*1000000)::bigint/1000000.0),
    '[default]Line1/PumpRunning', 'default',
    NULL, NULL, true, 'GOOD', 192, 'ignition-gateway',
    to_timestamp((extract(epoch from now())*1000000)::bigint/1000000.0),
    'BOOLEAN', NULL, NULL, false, NULL, false, NULL)
ON CONFLICT (event_time, event_id) DO NOTHING;
