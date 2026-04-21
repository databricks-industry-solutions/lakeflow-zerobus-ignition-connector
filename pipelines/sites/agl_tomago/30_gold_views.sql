-- Gold KPI views for AGL Tomago BESS demo

-- Site KPIs @ 5-minute grain (SoC, net power, tracking error, constraints, price)
CREATE OR REPLACE VIEW agl_ignition.ot.gold_site_kpis_5m AS
WITH base AS (
  SELECT
    window.start AS ts_5m,
    AVG(CASE WHEN signal_name = 'soc_pct' THEN value_numeric END) AS soc_pct_avg,
    AVG(CASE WHEN signal_name = 'poi_net_mw' THEN value_numeric END) AS poi_net_mw_avg,
    AVG(CASE WHEN signal_name = 'dispatch_target_mw' THEN value_numeric END) AS dispatch_target_mw_avg,
    AVG(CASE WHEN signal_name = 'curtailment_pct' THEN value_numeric END) AS curtailment_pct_avg,
    MAX(CASE WHEN signal_name = 'constraint_active' THEN value_numeric END) AS constraint_active_num,
    MAX(CASE WHEN signal_name = 'derate_active' THEN value_numeric END) AS derate_active_num,
    AVG(CASE WHEN signal_name = 'rrp_aud_per_mwh' THEN value_numeric END) AS rrp_aud_per_mwh_avg
  FROM agl_ignition.ot.silver_events_normalized
  WHERE asset_id IN ('tomago_site01', 'bess01', 'substation01', 'market')
  GROUP BY window(event_time, '5 minutes')
),
calc AS (
  SELECT
    ts_5m,
    soc_pct_avg,
    poi_net_mw_avg,
    dispatch_target_mw_avg,
    ABS(poi_net_mw_avg - dispatch_target_mw_avg) AS tracking_error_mw,
    curtailment_pct_avg,
    (constraint_active_num > 0.5) AS constraint_active,
    (derate_active_num > 0.5) AS derate_active,
    rrp_aud_per_mwh_avg
  FROM base
)
SELECT * FROM calc;

-- Daily rollup
CREATE OR REPLACE VIEW agl_ignition.ot.gold_site_kpis_daily AS
SELECT
  DATE_TRUNC('DAY', ts_5m) AS day,
  AVG(soc_pct_avg) AS soc_pct_avg,
  AVG(poi_net_mw_avg) AS poi_net_mw_avg,
  AVG(tracking_error_mw) AS tracking_error_mw_avg,
  AVG(curtailment_pct_avg) AS curtailment_pct_avg,
  MAX(CASE WHEN constraint_active THEN 1 ELSE 0 END) AS any_constraint,
  MAX(CASE WHEN derate_active THEN 1 ELSE 0 END) AS any_derate,
  AVG(rrp_aud_per_mwh_avg) AS rrp_aud_per_mwh_avg
FROM agl_ignition.ot.gold_site_kpis_5m
GROUP BY DATE_TRUNC('DAY', ts_5m);

-- Dispatch performance
CREATE OR REPLACE VIEW agl_ignition.ot.gold_dispatch_performance_5m AS
SELECT
  ts_5m,
  dispatch_target_mw_avg,
  poi_net_mw_avg,
  tracking_error_mw,
  constraint_active,
  derate_active
FROM agl_ignition.ot.gold_site_kpis_5m;

-- Asset reliability proxy (daily)
CREATE OR REPLACE VIEW agl_ignition.ot.gold_asset_reliability_daily AS
WITH daily AS (
  SELECT
    DATE_TRUNC('DAY', event_time) AS day,
    AVG(CASE WHEN signal_name = 'alarm_count' THEN value_numeric END) AS alarm_count_avg,
    MAX(CASE WHEN signal_name = 'critical_alarm_active' THEN value_numeric END) AS critical_alarm_num,
    AVG(CASE WHEN signal_name = 'max_rack_temp_c' THEN value_numeric END) AS max_rack_temp_c_avg
  FROM agl_ignition.ot.silver_events_normalized
  WHERE asset_id = 'bess01'
  GROUP BY DATE_TRUNC('DAY', event_time)
)
SELECT
  day,
  alarm_count_avg,
  (critical_alarm_num > 0.5) AS any_critical_alarm,
  max_rack_temp_c_avg
FROM daily;

-- Revenue proxy (daily): avg price * energy discharged minus charged (very rough demo)
CREATE OR REPLACE VIEW agl_ignition.ot.gold_revenue_proxy_daily AS
WITH p AS (
  SELECT
    DATE_TRUNC('DAY', ts_5m) AS day,
    AVG(rrp_aud_per_mwh_avg) AS rrp_avg
  FROM agl_ignition.ot.gold_site_kpis_5m
  GROUP BY DATE_TRUNC('DAY', ts_5m)
),
e AS (
  SELECT
    DATE_TRUNC('DAY', ts_5m) AS day,
    -- power MW averaged over 5m -> MWh = MW * (5/60)
    SUM(GREATEST(poi_net_mw_avg, 0.0)) * (5.0/60.0) AS discharged_mwh,
    SUM(GREATEST(-poi_net_mw_avg, 0.0)) * (5.0/60.0) AS charged_mwh
  FROM agl_ignition.ot.gold_site_kpis_5m
  GROUP BY DATE_TRUNC('DAY', ts_5m)
)
SELECT
  p.day,
  p.rrp_avg,
  e.discharged_mwh,
  e.charged_mwh,
  (e.discharged_mwh - e.charged_mwh) AS net_mwh,
  (e.discharged_mwh - e.charged_mwh) * p.rrp_avg AS revenue_proxy_aud
FROM p
JOIN e USING (day);

