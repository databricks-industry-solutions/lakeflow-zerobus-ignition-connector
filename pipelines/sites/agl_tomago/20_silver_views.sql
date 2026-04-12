-- Silver views for AGL Tomago BESS demo

-- 1) Resample to 1-minute grain (long-form)
CREATE OR REPLACE VIEW agl_ignition.ot.silver_signals_1m AS
SELECT
  asset_id,
  source_domain,
  signal_name,
  unit,
  window.start AS minute_ts,
  AVG(value_numeric) AS value_avg,
  MAX(value_numeric) AS value_max,
  MIN(value_numeric) AS value_min,
  COUNT(*) AS n
FROM agl_ignition.ot.silver_events_normalized
WHERE value_numeric IS NOT NULL
GROUP BY asset_id, source_domain, signal_name, unit, window(event_time, '1 minute');

-- 2) Latest values per signal
CREATE OR REPLACE VIEW agl_ignition.ot.silver_signals_latest AS
SELECT * EXCEPT(rn)
FROM (
  SELECT
    event_time,
    source_system,
    tag_provider,
    source_domain,
    asset_id,
    signal_name,
    unit,
    value_numeric,
    string_value,
    boolean_value,
    quality,
    quality_code,
    tag_path,
    ROW_NUMBER() OVER (PARTITION BY asset_id, signal_name ORDER BY event_time DESC) AS rn
  FROM agl_ignition.ot.silver_events_normalized
)
WHERE rn = 1;

-- 3) Grid events view (constraints / FCAS / voltage/frequency events)
CREATE OR REPLACE VIEW agl_ignition.ot.silver_grid_events AS
SELECT
  event_time,
  asset_id,
  signal_name,
  value_numeric,
  boolean_value,
  string_value,
  tag_path
FROM agl_ignition.ot.silver_events_normalized
WHERE source_domain = 'grid'
  AND signal_name IN ('constraint_active', 'curtailment_pct', 'fcas_enabled', 'poi_voltage_kv', 'poi_frequency_hz');

-- 4) Maintenance view
CREATE OR REPLACE VIEW agl_ignition.ot.silver_maintenance_events AS
SELECT
  event_time,
  asset_id,
  signal_name,
  value_numeric,
  boolean_value,
  string_value,
  tag_path
FROM agl_ignition.ot.silver_events_normalized
WHERE source_domain = 'cmms'
  AND signal_name IN ('open_work_orders', 'high_priority_work_orders', 'planned_outage_active', 'forced_outage_active');

