-- Silver convenience views (Saint-Gobain)

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

CREATE OR REPLACE VIEW ignition_demo.ot.silver_maintenance_events AS
SELECT
  ts_1m,
  asset_id,
  MAX(CASE WHEN signal_name = 'forced_outage' THEN value_last END) AS forced_outage_flag,
  MAX(CASE WHEN signal_name = 'active_work_orders' THEN value_last END) AS active_work_orders,
  MAX(CASE WHEN signal_name = 'high_priority_work_orders' THEN value_last END) AS high_priority_work_orders
FROM ignition_demo.ot.silver_signals_1m
WHERE source_domain = 'cmms'
GROUP BY ts_1m, asset_id;



