-- Dashboard query pack (Databricks SQL / AI/BI)
-- These queries assume you ran 10/11/20/30 files first.

-- ============================================================
-- Dashboard 1: Executive Ops Overview
-- ============================================================

-- Tile: Net export vs target (last 6 hours)
SELECT
  ts_5m,
  export_kw_avg AS export_kw,
  target_kw_avg AS target_kw,
  tracking_error_kw_avg AS error_kw,
  curtailment_pct_avg AS curtail_pct,
  rrp_avg AS rrp_aud_mwh
FROM ignition_demo.tilt_ot.gold_site_kpis_5m
WHERE ts_5m >= now() - INTERVAL 6 HOURS
ORDER BY ts_5m;

-- Tile: Latest KPIs
SELECT
  MAX_BY(export_kw_avg, ts_5m) AS export_kw_latest,
  MAX_BY(target_kw_avg, ts_5m) AS target_kw_latest,
  MAX_BY(curtailment_pct_avg, ts_5m) AS curtailment_pct_latest,
  MAX_BY(rrp_avg, ts_5m) AS rrp_latest,
  MAX_BY(bess_soc_pct_avg, ts_5m) AS bess_soc_latest,
  MAX_BY(active_work_orders_avg, ts_5m) AS active_wos_latest,
  MAX_BY(high_priority_work_orders_avg, ts_5m) AS high_wos_latest
FROM ignition_demo.tilt_ot.gold_site_kpis_5m;

-- ============================================================
-- Dashboard 2: Dispatch & Grid Compliance
-- ============================================================

-- Tracking error heatmap (hour x day)
SELECT
  date(ts_5m) AS dt,
  hour(ts_5m) AS hr,
  AVG(ABS(error_kw_avg)) AS avg_abs_error_kw
FROM ignition_demo.tilt_ot.gold_dispatch_performance_5m
GROUP BY date(ts_5m), hour(ts_5m)
ORDER BY dt DESC, hr;

-- Grid events timeline (last 6 hours)
SELECT
  ts_1m,
  constraint_active,
  frequency_event,
  voltage_sag_event,
  curtailment_pct,
  frequency_hz,
  voltage_kv
FROM ignition_demo.tilt_ot.silver_grid_events
WHERE ts_1m >= now() - INTERVAL 6 HOURS
ORDER BY ts_1m;

-- ============================================================
-- Dashboard 3: Asset Performance (Fleet)
-- ============================================================

-- Wind turbine power (last 6 hours)
SELECT
  ts_1m,
  MAX(CASE WHEN asset_id='t01' AND signal_name='power' THEN value_last END) AS t01_kw,
  MAX(CASE WHEN asset_id='t02' AND signal_name='power' THEN value_last END) AS t02_kw,
  MAX(CASE WHEN asset_id='t03' AND signal_name='power' THEN value_last END) AS t03_kw
FROM ignition_demo.tilt_ot.silver_signals_1m
WHERE ts_1m >= now() - INTERVAL 6 HOURS
GROUP BY ts_1m
ORDER BY ts_1m;

-- Solar inverter power + availability (last 6 hours)
SELECT
  ts_1m,
  MAX(CASE WHEN asset_id='inv01' AND signal_name='power' THEN value_last END) AS inv01_kw,
  MAX(CASE WHEN asset_id='inv02' AND signal_name='power' THEN value_last END) AS inv02_kw,
  MAX(CASE WHEN asset_id='inv01' AND signal_name='available' THEN value_last END) AS inv01_avail,
  MAX(CASE WHEN asset_id='inv02' AND signal_name='available' THEN value_last END) AS inv02_avail
FROM ignition_demo.tilt_ot.silver_signals_1m
WHERE ts_1m >= now() - INTERVAL 6 HOURS
GROUP BY ts_1m
ORDER BY ts_1m;

-- BESS SoC + net power (last 6 hours)
SELECT
  ts_1m,
  MAX(CASE WHEN asset_id='bess01' AND signal_name='soc' THEN value_last END) AS soc_pct,
  MAX(CASE WHEN asset_id='bess01' AND signal_name='net_power' THEN value_last END) AS net_kw
FROM ignition_demo.tilt_ot.silver_signals_1m
WHERE ts_1m >= now() - INTERVAL 6 HOURS
GROUP BY ts_1m
ORDER BY ts_1m;

-- ============================================================
-- Dashboard 4: Maintenance & Reliability
-- ============================================================

-- Work orders trend
SELECT
  ts_1m,
  MAX(CASE WHEN asset_id='site01' AND signal_name='active_work_orders' THEN value_last END) AS active_wos,
  MAX(CASE WHEN asset_id='site01' AND signal_name='high_priority_work_orders' THEN value_last END) AS high_wos
FROM ignition_demo.tilt_ot.silver_signals_1m
WHERE ts_1m >= now() - INTERVAL 24 HOURS
GROUP BY ts_1m
ORDER BY ts_1m;

-- Forced outage ratio by asset (last 7 days)
SELECT
  asset_id,
  AVG(forced_outage_ratio) AS forced_outage_ratio_7d
FROM ignition_demo.tilt_ot.gold_asset_reliability_daily
WHERE dt >= current_date() - INTERVAL 7 DAYS
GROUP BY asset_id
ORDER BY forced_outage_ratio_7d DESC;

-- ============================================================
-- Dashboard 5: Forecast & Planning
-- ============================================================

-- Forecast vs actual net power (last 6 hours)
SELECT
  ts_5m,
  export_kw_avg AS export_kw,
  net_forecast_h01_kw_avg AS net_forecast_kw,
  forecast_confidence_h01_pct_avg AS confidence_pct
FROM ignition_demo.tilt_ot.gold_site_kpis_5m
WHERE ts_5m >= now() - INTERVAL 6 HOURS
ORDER BY ts_5m;

-- Forecast accuracy hourly (last 7 days)
SELECT
  hr,
  mae_kw,
  mape,
  confidence_avg
FROM ignition_demo.tilt_ot.gold_forecast_accuracy_hourly
WHERE hr >= now() - INTERVAL 7 DAYS
ORDER BY hr;


