-- Dashboard query pack (AGL Tomago BESS demo)

-- 1) Last 6 hours: SoC + POI net power + dispatch target + price
SELECT
  ts_5m,
  soc_pct_avg,
  poi_net_mw_avg,
  dispatch_target_mw_avg,
  tracking_error_mw,
  curtailment_pct_avg,
  constraint_active,
  derate_active,
  rrp_aud_per_mwh_avg
FROM agl_ignition.ot.gold_site_kpis_5m
WHERE ts_5m >= current_timestamp() - INTERVAL 6 HOURS
ORDER BY ts_5m;

-- 2) Constraint periods today
SELECT
  ts_5m,
  curtailment_pct_avg,
  rrp_aud_per_mwh_avg
FROM agl_ignition.ot.gold_site_kpis_5m
WHERE DATE_TRUNC('DAY', ts_5m) = DATE_TRUNC('DAY', current_timestamp())
  AND constraint_active = true
ORDER BY ts_5m;

-- 3) Tracking error distribution (last 24h)
SELECT
  approx_percentile(tracking_error_mw, 0.50) AS p50_mw,
  approx_percentile(tracking_error_mw, 0.90) AS p90_mw,
  approx_percentile(tracking_error_mw, 0.99) AS p99_mw
FROM agl_ignition.ot.gold_site_kpis_5m
WHERE ts_5m >= current_timestamp() - INTERVAL 24 HOURS;

-- 4) Maintenance snapshot
SELECT *
FROM agl_ignition.ot.silver_signals_latest
WHERE source_domain = 'cmms'
ORDER BY signal_name;

