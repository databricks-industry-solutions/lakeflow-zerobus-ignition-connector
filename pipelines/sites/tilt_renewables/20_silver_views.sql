-- Silver convenience views for dashboards + Genie

-- 1) Resample to 1-minute buckets (avg + last)
CREATE OR REPLACE VIEW ignition_demo.ot.silver_signals_1m AS
WITH base AS (
  SELECT
    date_trunc('minute', event_time) AS ts_1m,
    asset_id,
    signal_name,
    unit,
    source_domain,
    value_numeric,
    string_value,
    quality,
    tag_path,
    event_time
  FROM ignition_demo.ot.silver_events_normalized
  WHERE asset_id IS NOT NULL AND signal_name IS NOT NULL
)
SELECT
  ts_1m,
  asset_id,
  signal_name,
  unit,
  source_domain,
  AVG(value_numeric) AS value_avg,
  MAX_BY(value_numeric, event_time) AS value_last,
  MAX_BY(string_value, event_time) AS string_last,
  MAX_BY(quality, event_time) AS quality_last,
  MAX_BY(tag_path, event_time) AS tag_path_last
FROM base
GROUP BY ts_1m, asset_id, signal_name, unit, source_domain;

-- 2) Latest values per asset/signal (for tiles)
CREATE OR REPLACE VIEW ignition_demo.ot.silver_signals_latest AS
SELECT
  asset_id,
  signal_name,
  unit,
  source_domain,
  MAX_BY(value_numeric, event_time) AS value_latest,
  MAX_BY(string_value, event_time) AS string_latest,
  MAX(event_time) AS event_time_latest
FROM ignition_demo.ot.silver_events_normalized
WHERE asset_id IS NOT NULL AND signal_name IS NOT NULL
GROUP BY asset_id, signal_name, unit, source_domain;

-- 3) Grid events (interval windows)
CREATE OR REPLACE VIEW ignition_demo.ot.silver_grid_events AS
WITH x AS (
  SELECT
    ts_1m,
    MAX(CASE WHEN asset_id = 'poi' AND signal_name = 'constraint_active' THEN value_last END) AS constraint_active,
    MAX(CASE WHEN asset_id = 'poi' AND signal_name = 'curtailment' THEN value_last END) AS curtailment_pct,
    MAX(CASE WHEN asset_id = 'poi' AND signal_name = 'frequency' THEN value_last END) AS frequency_hz,
    MAX(CASE WHEN asset_id = 'poi' AND signal_name = 'voltage' THEN value_last END) AS voltage_kv
  FROM ignition_demo.ot.silver_signals_1m
  GROUP BY ts_1m
)
SELECT
  ts_1m,
  constraint_active,
  curtailment_pct,
  frequency_hz,
  voltage_kv,
  CASE WHEN frequency_hz IS NOT NULL AND ABS(frequency_hz - 50.0) >= 0.15 THEN true ELSE false END AS frequency_event,
  CASE WHEN voltage_kv IS NOT NULL AND voltage_kv <= 65.2 THEN true ELSE false END AS voltage_sag_event
FROM x;

-- 4) Maintenance events (simple)
CREATE OR REPLACE VIEW ignition_demo.ot.silver_maintenance_events AS
WITH x AS (
  SELECT
    ts_1m,
    MAX(CASE WHEN signal_name = 'active_work_orders' THEN value_last END) AS active_work_orders,
    MAX(CASE WHEN signal_name = 'high_priority_work_orders' THEN value_last END) AS high_priority_work_orders,
    MAX(CASE WHEN signal_name = 'forced_outage' THEN value_last END) AS forced_outage_flag,
    asset_id
  FROM ignition_demo.ot.silver_signals_1m
  WHERE source_domain = 'cmms'
  GROUP BY ts_1m, asset_id
)
SELECT * FROM x;



