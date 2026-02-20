-- Gold KPI views (business story)

-- Helper: site-level 1m pivot
CREATE OR REPLACE VIEW ignition_demo.renewables_co_ot._site01_1m AS
SELECT
  ts_1m,
  MAX(CASE WHEN asset_id='poi' AND signal_name='net_power' THEN value_last END) AS poi_net_kw,
  MAX(CASE WHEN asset_id='poi' AND signal_name='export_power' THEN value_last END) AS poi_export_kw,
  MAX(CASE WHEN asset_id='poi' AND signal_name='import_power' THEN value_last END) AS poi_import_kw,
  MAX(CASE WHEN asset_id='poi' AND signal_name='dispatch_target' THEN value_last END) AS dispatch_target_kw,
  MAX(CASE WHEN asset_id='poi' AND signal_name='curtailment' THEN value_last END) AS curtailment_pct,
  MAX(CASE WHEN asset_id='poi' AND signal_name='constraint_active' THEN value_last END) AS constraint_active,
  MAX(CASE WHEN asset_id='poi' AND signal_name='rrp' THEN value_last END) AS rrp_aud_mwh,
  MAX(CASE WHEN asset_id='windfarm01' AND signal_name='power' THEN value_last END) AS wind_kw,
  MAX(CASE WHEN asset_id='solarfarm01' AND signal_name='power' THEN value_last END) AS solar_kw,
  MAX(CASE WHEN asset_id='bess01' AND signal_name='net_power' THEN value_last END) AS bess_kw,
  MAX(CASE WHEN asset_id='bess01' AND signal_name='soc' THEN value_last END) AS bess_soc_pct,
  MAX(CASE WHEN asset_id='site01' AND signal_name='net_power_forecast_h01' THEN value_last END) AS net_forecast_h01_kw,
  MAX(CASE WHEN asset_id='site01' AND signal_name='forecast_confidence_h01' THEN value_last END) AS forecast_confidence_h01_pct,
  MAX(CASE WHEN asset_id='site01' AND signal_name='expected_curtailment_h01' THEN value_last END) AS expected_curtailment_h01_pct,
  MAX(CASE WHEN asset_id='site01' AND signal_name='active_work_orders' THEN value_last END) AS active_work_orders,
  MAX(CASE WHEN asset_id='site01' AND signal_name='high_priority_work_orders' THEN value_last END) AS high_priority_work_orders
FROM ignition_demo.renewables_co_ot.silver_signals_1m
GROUP BY ts_1m;

-- 1) Site KPIs (5-minute)
CREATE OR REPLACE VIEW ignition_demo.renewables_co_ot.gold_site_kpis_5m AS
SELECT
  ts_5m,
  export_kw_avg,
  target_kw_avg,
  tracking_error_kw_avg,
  curtailment_pct_avg,
  constraint_active_any,
  rrp_avg,
  wind_kw_avg,
  solar_kw_avg,
  bess_kw_avg,
  bess_soc_pct_avg,
  active_work_orders_avg,
  high_priority_work_orders_avg,
  net_forecast_h01_kw_avg,
  forecast_confidence_h01_pct_avg
FROM (
  SELECT
    -- 5-minute bucket start (Databricks-compatible)
    to_timestamp(from_unixtime(floor(unix_timestamp(ts_1m) / 300) * 300)) AS ts_5m,
    AVG(poi_export_kw) AS export_kw_avg,
    AVG(dispatch_target_kw) AS target_kw_avg,
    AVG(poi_export_kw - dispatch_target_kw) AS tracking_error_kw_avg,
    AVG(curtailment_pct) AS curtailment_pct_avg,
    MAX(constraint_active) AS constraint_active_any,
    AVG(rrp_aud_mwh) AS rrp_avg,
    AVG(wind_kw) AS wind_kw_avg,
    AVG(solar_kw) AS solar_kw_avg,
    AVG(bess_kw) AS bess_kw_avg,
    AVG(bess_soc_pct) AS bess_soc_pct_avg,
    AVG(active_work_orders) AS active_work_orders_avg,
    AVG(high_priority_work_orders) AS high_priority_work_orders_avg,
    AVG(net_forecast_h01_kw) AS net_forecast_h01_kw_avg,
    AVG(forecast_confidence_h01_pct) AS forecast_confidence_h01_pct_avg
  FROM ignition_demo.renewables_co_ot._site01_1m
  GROUP BY to_timestamp(from_unixtime(floor(unix_timestamp(ts_1m) / 300) * 300))
) agg;

-- 2) Daily KPIs (energy + curtailment + revenue proxy)
CREATE OR REPLACE VIEW ignition_demo.renewables_co_ot.gold_site_kpis_daily AS
WITH x AS (
  SELECT
    ts_1m,
    poi_export_kw,
    dispatch_target_kw,
    curtailment_pct,
    rrp_aud_mwh
  FROM ignition_demo.renewables_co_ot._site01_1m
),
daily AS (
  SELECT
    date(ts_1m) AS dt,
    AVG(poi_export_kw) AS export_kw_avg,
    AVG(dispatch_target_kw) AS target_kw_avg,
    AVG(ABS(poi_export_kw - dispatch_target_kw)) AS tracking_mae_kw,
    AVG(curtailment_pct) AS curtailment_pct_avg,
    SUM(poi_export_kw) / 60.0 AS export_kwh_proxy, -- 1-minute samples, proxy only
    AVG(rrp_aud_mwh) AS rrp_avg
  FROM x
  GROUP BY date(ts_1m)
)
SELECT
  dt,
  export_kw_avg,
  target_kw_avg,
  tracking_mae_kw,
  curtailment_pct_avg,
  export_kwh_proxy,
  (export_kwh_proxy / 1000.0) * rrp_avg AS revenue_proxy_aud
FROM daily;

-- 3) Dispatch performance (5m buckets, pass/fail)
CREATE OR REPLACE VIEW ignition_demo.renewables_co_ot.gold_dispatch_performance_5m AS
WITH x AS (
  SELECT
    ts_1m,
    poi_export_kw,
    dispatch_target_kw
  FROM ignition_demo.renewables_co_ot._site01_1m
  WHERE poi_export_kw IS NOT NULL AND dispatch_target_kw IS NOT NULL
),
agg AS (
  SELECT
    to_timestamp(from_unixtime(floor(unix_timestamp(ts_1m) / 300) * 300)) AS ts_5m,
    AVG(poi_export_kw) AS export_kw_avg,
    AVG(dispatch_target_kw) AS target_kw_avg,
    AVG(poi_export_kw - dispatch_target_kw) AS error_kw_avg,
    AVG(ABS(poi_export_kw - dispatch_target_kw)) AS mae_kw,
    AVG(CASE WHEN ABS(poi_export_kw - dispatch_target_kw) <= 250.0 THEN 1 ELSE 0 END) AS pct_intervals_within_250kw
  FROM x
  GROUP BY to_timestamp(from_unixtime(floor(unix_timestamp(ts_1m) / 300) * 300))
)
SELECT
  ts_5m,
  export_kw_avg,
  target_kw_avg,
  error_kw_avg,
  mae_kw,
  pct_intervals_within_250kw
FROM agg;

-- 4) Forecast accuracy (hourly)
CREATE OR REPLACE VIEW ignition_demo.renewables_co_ot.gold_forecast_accuracy_hourly AS
WITH x AS (
  SELECT
    ts_1m,
    poi_net_kw,
    net_forecast_h01_kw,
    forecast_confidence_h01_pct
  FROM ignition_demo.renewables_co_ot._site01_1m
  WHERE poi_net_kw IS NOT NULL AND net_forecast_h01_kw IS NOT NULL
),
agg AS (
  SELECT
    date_trunc('hour', ts_1m) AS hr,
    AVG(ABS(poi_net_kw - net_forecast_h01_kw)) AS mae_kw,
    AVG(CASE WHEN ABS(net_forecast_h01_kw) < 1 THEN NULL ELSE ABS((poi_net_kw - net_forecast_h01_kw) / net_forecast_h01_kw) END) AS mape,
    AVG(forecast_confidence_h01_pct) AS confidence_avg
  FROM x
  GROUP BY date_trunc('hour', ts_1m)
)
SELECT * FROM agg;

-- 5) Reliability (daily outages/work orders proxy)
CREATE OR REPLACE VIEW ignition_demo.renewables_co_ot.gold_asset_reliability_daily AS
WITH x AS (
  SELECT
    date(ts_1m) AS dt,
    asset_id,
    AVG(forced_outage_flag) AS forced_outage_ratio,
    MAX(active_work_orders) AS active_work_orders_max,
    MAX(high_priority_work_orders) AS high_priority_work_orders_max
  FROM ignition_demo.renewables_co_ot.silver_maintenance_events
  GROUP BY date(ts_1m), asset_id
)
SELECT * FROM x;

-- 6) Revenue proxy (daily) re-exposed for dashboards
CREATE OR REPLACE VIEW ignition_demo.renewables_co_ot.gold_revenue_proxy_daily AS
SELECT
  dt,
  revenue_proxy_aud
FROM ignition_demo.renewables_co_ot.gold_site_kpis_daily;


