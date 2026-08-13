-- 1. Timestamps must be TODAY (not 1970) — proves micros conversion is correct.
SELECT event_id, data_type,
       event_time AT TIME ZONE 'Australia/Sydney' AS event_time_aedt,
       numeric_value, boolean_value,
       (event_time > now() - interval '5 min') AS ts_is_fresh
FROM ign_val.ignition_tag_events
ORDER BY event_id;

-- 2. Null-coercion: the BOOLEAN row must have numeric_value = NULL (not 0.0).
SELECT
  (SELECT numeric_value FROM ign_val.ignition_tag_events WHERE event_id='evt-bool-1') IS NULL
    AS bool_row_numeric_is_null,
  (SELECT numeric_value FROM ign_val.ignition_tag_events WHERE event_id='evt-num-1')
    AS num_row_numeric_value;

-- 3. LVC populated with current values (the HMI read path).
SELECT tag_path, numeric_value, boolean_value, data_type
FROM ign_val._lvc_ignition_tag_events
ORDER BY tag_path;

-- 4. Row count before the replay test.
SELECT count(*) AS rows_before_replay FROM ign_val.ignition_tag_events;
