## AGL Tomago — Dashboard Agent Prompts (Lakeview / AI/BI)

Use this file to create a **master dashboard** + **sub-dashboards** via the dashboard agent.

### AGL brand palette (from AGL public logo SVG)

- Deep navy: `#001CB0`
- Primary blue: `#005FC5`
- Azure: `#0096D6`
- Bright cyan: `#00BEE3`
- Cyan: `#00D6EA`
- Light cyan: `#00DFED`
- Aqua highlight: `#4CE9F2`
- Text/black: `#000000`
- Background/white: `#FFFFFF`
- Neutral gridlines: `#E6EEF6`

---

## Master dashboard prompt

```text
Create a Lakeview (AI/BI) dashboard named “AGL Tomago Battery — Executive Overview”.

Brand theme (apply globally):
- Background: #FFFFFF
- Primary: #005FC5
- Secondary: #0096D6
- Accent: #00D6EA (use sparingly)
- Critical highlight: #001CB0
- Text: #000000
- Gridlines/dividers: #E6EEF6

Layout:
- Row 1: KPI snapshot tiles (single value cards)
- Row 2: 6-hour trends (line charts)
- Row 3: Exceptions + Data freshness (tables)

For all line charts: use Primary (#005FC5) for actuals, Secondary (#0096D6) for targets, Accent (#00D6EA) for price, Critical (#001CB0) for tracking error.
```

### Tile: KPI Snapshot (latest)

```text
Add tile titled “Latest KPIs (as of latest 5m)”.
Visualization: KPI cards (or a small 1-row table if needed).
Apply AGL theme.

SQL:
SELECT
  ts_5m,
  soc_pct_avg,
  poi_net_mw_avg,
  dispatch_target_mw_avg,
  tracking_error_mw,
  constraint_active,
  derate_active,
  curtailment_pct_avg,
  rrp_aud_per_mwh_avg
FROM agl_ignition.ot.gold_site_kpis_5m
ORDER BY ts_5m DESC
LIMIT 1;
```

### Tile: Trend (last 6 hours)

```text
Add tile titled “Last 6 hours — SoC, POI MW, Target MW, Tracking Error”.
Visualization: multi-series line chart.
Colors: POI MW = #005FC5, Target MW = #0096D6, Tracking Error = #001CB0, SoC = #00D6EA.

SQL:
SELECT
  ts_5m,
  soc_pct_avg,
  poi_net_mw_avg,
  dispatch_target_mw_avg,
  tracking_error_mw,
  constraint_active,
  derate_active,
  rrp_aud_per_mwh_avg
FROM agl_ignition.ot.gold_site_kpis_5m
WHERE ts_5m >= current_timestamp() - INTERVAL 6 HOURS
ORDER BY ts_5m;
```

### Tile: Data freshness by domain

```text
Add tile titled “Ingestion freshness by domain”.
Visualization: table (sortable).
Theme: header background #E6EEF6.

SQL:
SELECT
  source_domain,
  MAX(event_time) AS last_event_time,
  MAX(ingestion_timestamp) AS last_ingestion_timestamp
FROM agl_ignition.ot.silver_events_normalized
GROUP BY source_domain
ORDER BY source_domain;
```

### Tile: Today constraint/derate minutes + curtailment avg

```text
Add tile titled “Today — Constraint & Derate Minutes, Curtailment”.
Visualization: table (or bar + single value).
Colors: constraint = #001CB0, derate = #005FC5, curtailment highlight = #00D6EA.

SQL:
WITH k AS (
  SELECT *
  FROM agl_ignition.ot.gold_site_kpis_5m
  WHERE ts_5m >= date_trunc('day', current_timestamp())
)
SELECT
  date_trunc('day', ts_5m) AS day,
  SUM(CASE WHEN constraint_active THEN 1 ELSE 0 END) * 5 AS constraint_minutes,
  SUM(CASE WHEN derate_active THEN 1 ELSE 0 END) * 5 AS derate_minutes,
  AVG(curtailment_pct_avg) AS curtailment_pct_avg
FROM k
GROUP BY date_trunc('day', ts_5m);
```

---

## Sub-dashboard: Dispatch Performance

```text
Create a sub-dashboard named “AGL Tomago — Dispatch Performance”.
Apply the same AGL theme.

Layout:
- Row 1: Worst intervals table
- Row 2: Tracking error by hour (trend)
- Row 3: Target vs actual (trend)
```

### Tile: Worst tracking-error intervals (last 2 hours)

```text
Add tile titled “Worst Tracking Error — Last 2 Hours”.
Visualization: table.

SQL:
SELECT
  ts_5m,
  dispatch_target_mw_avg,
  poi_net_mw_avg,
  tracking_error_mw,
  constraint_active,
  derate_active
FROM agl_ignition.ot.gold_dispatch_performance_5m
WHERE ts_5m >= current_timestamp() - INTERVAL 2 HOURS
ORDER BY tracking_error_mw DESC
LIMIT 25;
```

### Tile: Tracking error by hour (last 24 hours)

```text
Add tile titled “Tracking Error — Hourly (Last 24 Hours)”.
Visualization: line chart with 3 series (avg, max, p95).
Colors: avg = #005FC5, p95 = #0096D6, max = #001CB0.

SQL:
SELECT
  date_trunc('hour', ts_5m) AS hour_ts,
  AVG(tracking_error_mw) AS tracking_error_mw_avg,
  MAX(tracking_error_mw) AS tracking_error_mw_max,
  percentile_approx(tracking_error_mw, 0.95) AS tracking_error_mw_p95
FROM agl_ignition.ot.gold_dispatch_performance_5m
WHERE ts_5m >= current_timestamp() - INTERVAL 24 HOURS
GROUP BY date_trunc('hour', ts_5m)
ORDER BY hour_ts;
```

### Tile: Target vs actual (last 6 hours)

```text
Add tile titled “Target vs Actual — Last 6 Hours”.
Visualization: line chart (target + actual) plus optional error as secondary axis.
Colors: target = #0096D6, actual = #005FC5, error = #001CB0.

SQL:
SELECT
  ts_5m,
  dispatch_target_mw_avg,
  poi_net_mw_avg,
  tracking_error_mw
FROM agl_ignition.ot.gold_dispatch_performance_5m
WHERE ts_5m >= current_timestamp() - INTERVAL 6 HOURS
ORDER BY ts_5m;
```

---

## Sub-dashboard: Reliability & Thermal Risk

```text
Create a sub-dashboard named “AGL Tomago — Reliability & Thermal”.
Apply the same AGL theme.
```

### Tile: Latest alarm/temp snapshot

```text
Add tile titled “Latest Reliability Snapshot”.
Visualization: KPI cards (alarm_count, critical_alarm_active, max_rack_temp_c) + as_of.
Colors: normal values #005FC5; critical alarm highlight #001CB0.

SQL:
SELECT
  MAX(CASE WHEN signal_name = 'alarm_count' THEN value_numeric END) AS alarm_count,
  MAX(CASE WHEN signal_name = 'critical_alarm_active' THEN boolean_value END) AS critical_alarm_active,
  MAX(CASE WHEN signal_name = 'max_rack_temp_c' THEN value_numeric END) AS max_rack_temp_c,
  MAX(event_time) AS as_of
FROM agl_ignition.ot.silver_signals_latest
WHERE asset_id = 'bess01'
  AND signal_name IN ('alarm_count', 'critical_alarm_active', 'max_rack_temp_c');
```

### Tile: Reliability proxy (daily, last 30 days)

```text
Add tile titled “Daily Reliability Proxy (Last 30 Days)”.
Visualization: line chart + marker/flag for any_critical_alarm.
Colors: alarm_count_avg = #005FC5, max_rack_temp_c_avg = #00D6EA, critical flag = #001CB0.

SQL:
SELECT
  day,
  alarm_count_avg,
  any_critical_alarm,
  max_rack_temp_c_avg
FROM agl_ignition.ot.gold_asset_reliability_daily
WHERE day >= date_sub(current_date(), 30)
ORDER BY day;
```

### Tile: Thermal trend (last 24 hours, 1-minute)

```text
Add tile titled “Max Rack Temp (1m) — Last 24 Hours”.
Visualization: line chart.
Color: #00D6EA.

SQL:
SELECT
  minute_ts,
  value_avg AS max_rack_temp_c_avg_1m
FROM agl_ignition.ot.silver_signals_1m
WHERE asset_id = 'bess01'
  AND signal_name = 'max_rack_temp_c'
  AND minute_ts >= current_timestamp() - INTERVAL 24 HOURS
ORDER BY minute_ts;
```

---

## Sub-dashboard: Revenue Proxy / Market Impact

```text
Create a sub-dashboard named “AGL Tomago — Revenue / Market Proxy”.
Apply the same AGL theme.
```

### Tile: Revenue proxy (daily, last 60 days)

```text
Add tile titled “Revenue Proxy (Daily) — Last 60 Days”.
Visualization: line chart (revenue_proxy_aud) + optional secondary for net_mwh.
Colors: revenue_proxy_aud = #005FC5, net_mwh = #0096D6, rrp_avg = #00D6EA.

SQL:
SELECT
  day,
  rrp_avg,
  discharged_mwh,
  charged_mwh,
  net_mwh,
  revenue_proxy_aud
FROM agl_ignition.ot.gold_revenue_proxy_daily
WHERE day >= date_sub(current_date(), 60)
ORDER BY day;
```

---

## Sub-dashboard: Grid & Constraints

```text
Create a sub-dashboard named “AGL Tomago — Grid & Constraints”.
Apply the same AGL theme.
```

### Tile: Constraint + curtailment (last 24 hours)

```text
Add tile titled “Constraints & Curtailment — Last 24 Hours”.
Visualization: line (curtailment) + marker/band (constraint active).
Colors: curtailment = #00D6EA, constraint markers = #001CB0.

SQL:
SELECT
  date_trunc('hour', event_time) AS hour_ts,
  MAX(CASE WHEN signal_name = 'constraint_active' THEN boolean_value END) AS constraint_active,
  AVG(CASE WHEN signal_name = 'curtailment_pct' THEN value_numeric END) AS curtailment_pct_avg
FROM agl_ignition.ot.silver_grid_events
WHERE asset_id = 'tomago_site01'
  AND event_time >= current_timestamp() - INTERVAL 24 HOURS
  AND signal_name IN ('constraint_active','curtailment_pct')
GROUP BY date_trunc('hour', event_time)
ORDER BY hour_ts;
```

---

## Sub-dashboard: Maintenance / CMMS

```text
Create a sub-dashboard named “AGL Tomago — Maintenance / CMMS”.
Apply the same AGL theme.
```

### Tile: Work orders + outages (latest)

```text
Add tile titled “Latest Work Orders & Outages”.
Visualization: KPI cards + as_of.
Colors: counts = #005FC5; outage-active highlight = #001CB0.

SQL:
SELECT
  MAX(CASE WHEN signal_name = 'open_work_orders' THEN value_numeric END) AS open_work_orders,
  MAX(CASE WHEN signal_name = 'high_priority_work_orders' THEN value_numeric END) AS high_priority_work_orders,
  MAX(CASE WHEN signal_name = 'planned_outage_active' THEN boolean_value END) AS planned_outage_active,
  MAX(CASE WHEN signal_name = 'forced_outage_active' THEN boolean_value END) AS forced_outage_active,
  MAX(event_time) AS as_of
FROM agl_ignition.ot.silver_signals_latest
WHERE asset_id = 'cmms'
  AND signal_name IN ('open_work_orders','high_priority_work_orders','planned_outage_active','forced_outage_active');
```

