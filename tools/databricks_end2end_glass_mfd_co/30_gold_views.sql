-- Gold KPI views (Glass Mfd Co glass line demo)

-- Pivot key signals to 1m grain
CREATE OR REPLACE VIEW ignition_demo.glass_mfd_co_ot._sg_site01_1m AS
SELECT
  ts_1m,
  MAX(CASE WHEN asset_id='sg_site01' AND signal_name='throughput' THEN value_last END) AS throughput_upm,
  MAX(CASE WHEN asset_id='sg_site01' AND signal_name='scrap_rate' THEN value_last END) AS scrap_pct,
  MAX(CASE WHEN asset_id='sg_cut' AND signal_name='quality_score' THEN value_last END) AS quality_score,
  MAX(CASE WHEN asset_id='sg_site01' AND signal_name='target_throughput' THEN value_last END) AS target_upm,
  MAX(CASE WHEN asset_id='sg_site01' AND signal_name='curtailment' THEN value_last END) AS curtail_pct,
  MAX(CASE WHEN asset_id='sg_site01' AND signal_name='gas_price' THEN value_last END) AS gas_price_eur_gj,
  MAX(CASE WHEN asset_id='sg_site01' AND signal_name='elec_price' THEN value_last END) AS elec_price_eur_mwh,
  MAX(CASE WHEN asset_id='sg_site01' AND signal_name='active_work_orders' THEN value_last END) AS active_wos,
  MAX(CASE WHEN asset_id='sg_site01' AND signal_name='high_priority_work_orders' THEN value_last END) AS high_wos,
  MAX(CASE WHEN asset_id='sg_site01' AND signal_name='throughput_forecast_h01' THEN value_last END) AS thr_forecast_h01,
  MAX(CASE WHEN asset_id='sg_site01' AND signal_name='scrap_forecast_h01' THEN value_last END) AS scrap_forecast_h01,
  MAX(CASE WHEN asset_id='sg_site01' AND signal_name='forecast_confidence_h01' THEN value_last END) AS forecast_confidence_h01
FROM ignition_demo.glass_mfd_co_ot.silver_signals_1m
GROUP BY ts_1m;

-- 5-minute KPIs
CREATE OR REPLACE VIEW ignition_demo.glass_mfd_co_ot.gold_site_kpis_5m AS
SELECT
  to_timestamp(from_unixtime(floor(unix_timestamp(ts_1m) / 300) * 300)) AS ts_5m,
  AVG(throughput_upm) AS throughput_upm_avg,
  AVG(target_upm) AS target_upm_avg,
  AVG(throughput_upm - target_upm) AS throughput_error_avg,
  AVG(scrap_pct) AS scrap_pct_avg,
  AVG(quality_score) AS quality_score_avg,
  AVG(curtail_pct) AS curtail_pct_avg,
  AVG(gas_price_eur_gj) AS gas_price_avg,
  AVG(elec_price_eur_mwh) AS elec_price_avg,
  AVG(active_wos) AS active_wos_avg,
  AVG(high_wos) AS high_wos_avg,
  AVG(thr_forecast_h01) AS thr_forecast_h01_avg,
  AVG(forecast_confidence_h01) AS forecast_confidence_h01_avg
FROM ignition_demo.glass_mfd_co_ot._sg_site01_1m
GROUP BY to_timestamp(from_unixtime(floor(unix_timestamp(ts_1m) / 300) * 300));

-- Daily KPIs + cost proxy
CREATE OR REPLACE VIEW ignition_demo.glass_mfd_co_ot.gold_site_kpis_daily AS
WITH x AS (
  SELECT
    date(ts_1m) AS dt,
    throughput_upm,
    scrap_pct,
    quality_score,
    gas_price_eur_gj,
    elec_price_eur_mwh
  FROM ignition_demo.glass_mfd_co_ot._sg_site01_1m
)
SELECT
  dt,
  AVG(throughput_upm) AS throughput_upm_avg,
  AVG(scrap_pct) AS scrap_pct_avg,
  AVG(quality_score) AS quality_score_avg,
  AVG(gas_price_eur_gj) AS gas_price_avg,
  AVG(elec_price_eur_mwh) AS elec_price_avg,
  -- rough cost proxy: gas flow isn't modeled in this view; proxy cost = throughput * price multipliers
  (AVG(throughput_upm) * 0.02) * AVG(gas_price_eur_gj) AS gas_cost_proxy_eur_per_min,
  (AVG(throughput_upm) * 0.001) * AVG(elec_price_eur_mwh) AS elec_cost_proxy_eur_per_min
FROM x
GROUP BY dt;

-- Forecast accuracy (hourly)
CREATE OR REPLACE VIEW ignition_demo.glass_mfd_co_ot.gold_forecast_accuracy_hourly AS
WITH x AS (
  SELECT
    ts_1m,
    throughput_upm,
    thr_forecast_h01,
    forecast_confidence_h01
  FROM ignition_demo.glass_mfd_co_ot._sg_site01_1m
  WHERE throughput_upm IS NOT NULL AND thr_forecast_h01 IS NOT NULL
)
SELECT
  date_trunc('hour', ts_1m) AS hr,
  AVG(ABS(throughput_upm - thr_forecast_h01)) AS mae_upm,
  AVG(forecast_confidence_h01) AS confidence_avg
FROM x
GROUP BY date_trunc('hour', ts_1m);


