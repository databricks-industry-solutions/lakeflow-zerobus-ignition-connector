## Genie room seed: “Saint-Gobain Site01 Operations”

This file is a **copy/paste runbook** for setting up a Genie room so you can demo “ask questions about OT data” using the Saint-Gobain Silver/Gold layer.

### 1) Create the Genie room

In Databricks:

- Go to **Genie**
- Create a room named: **Saint-Gobain Site01 Operations**
- Set the room description to something like:
  - “Operations analytics for a glass line. Use Gold KPIs for answers; drill into Silver signals for root cause.”

### 2) Add data sources (tables/views) to the room

Add these as data sources so Genie can query them.

#### Suggested data sources to add

- Gold:
  - `ignition_demo.saint_ot.gold_site_kpis_5m`
  - `ignition_demo.saint_ot.gold_site_kpis_daily`
  - `ignition_demo.saint_ot.gold_forecast_accuracy_hourly`
- Silver (drilldown):
  - `ignition_demo.saint_ot.silver_signals_1m`
  - `ignition_demo.saint_ot.silver_signals_latest`
  - `ignition_demo.saint_ot.silver_maintenance_events`

Tip: If you want Genie to stay “executive friendly”, add **Gold only** first, then add the Silver drilldown tables once the room is answering well.

### 3) Suggested “instructions” (system prompt) for the room

Paste something like this into the Genie room instructions:

```text
You are an OT operations analyst for a Saint-Gobain glass line (demo).
Prefer the Gold KPI views for summaries and trends. Use Silver only for drilldown/root cause.
Assume all data is for Site01 unless the user asks otherwise.
When comparing signals, align to the same time grain (5m for gold_site_kpis_5m, 1m for silver_signals_1m).
If asked “why”, look for these common drivers:
- constraints (curtailment/constraint_active)
- maintenance (forced_outage_flag, work order backlog)
- quality / scrap rising
Always include the time window you used in your query.
```

### 4) High-signal questions (copy/paste)

- “Why is throughput below target right now?”
- “Is scrap rate increasing? What changed first: furnace temps, vibration, or quality score?”
- “Show the last 6 hours of throughput vs target and scrap %.”
- “Are there any forced outages active (furnace/conveyor/cutting)?”
- “How many active work orders do we have and how many are high priority?”
- “How accurate is the next-hour throughput forecast today?”
- “Estimate cost impact when electricity price spikes (using proxy).”

### 5) Demo-friendly “guided questions” (with hints)

- “What happened in the last 30 minutes?”
  - Hint: use `gold_site_kpis_5m` and look for changes in `throughput_upm_avg`, `scrap_pct_avg`, `quality_score_avg`, `curtail_pct_avg`.
- “Show me the top 3 drivers correlated with scrap increasing today.”
  - Hint: drill into `silver_signals_1m` for furnace temps, vibration, thickness, blade temp (if present).
- “Are we constrained or maintenance-limited right now?”
  - Hint: compare `curtail_pct_avg` / constraint vs `forced_outage_flag` and work orders.


