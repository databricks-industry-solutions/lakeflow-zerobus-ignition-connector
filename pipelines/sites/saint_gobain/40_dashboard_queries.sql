-- Dashboard query pack (Saint-Gobain)

-- Executive overview (last 6 hours)
SELECT
  ts_5m,
  throughput_upm_avg,
  target_upm_avg,
  throughput_error_avg,
  scrap_pct_avg,
  quality_score_avg,
  curtail_pct_avg,
  gas_price_avg,
  elec_price_avg,
  active_wos_avg,
  high_wos_avg
FROM ignition_demo.ot.gold_site_kpis_5m
WHERE ts_5m >= now() - INTERVAL 6 HOURS
ORDER BY ts_5m;

-- Latest tiles
SELECT
  MAX_BY(throughput_upm_avg, ts_5m) AS throughput_latest,
  MAX_BY(scrap_pct_avg, ts_5m) AS scrap_latest,
  MAX_BY(quality_score_avg, ts_5m) AS quality_latest,
  MAX_BY(gas_price_avg, ts_5m) AS gas_price_latest,
  MAX_BY(elec_price_avg, ts_5m) AS elec_price_latest,
  MAX_BY(active_wos_avg, ts_5m) AS active_wos_latest
FROM ignition_demo.ot.gold_site_kpis_5m;

-- Maintenance drilldown (forced outage flags last 24h)
SELECT
  ts_1m,
  asset_id,
  forced_outage_flag,
  active_work_orders,
  high_priority_work_orders
FROM ignition_demo.ot.silver_maintenance_events
WHERE ts_1m >= now() - INTERVAL 24 HOURS
ORDER BY ts_1m DESC, asset_id;

-- Forecast accuracy (7d)
SELECT *
FROM ignition_demo.ot.gold_forecast_accuracy_hourly
WHERE hr >= now() - INTERVAL 7 DAYS
ORDER BY hr;



