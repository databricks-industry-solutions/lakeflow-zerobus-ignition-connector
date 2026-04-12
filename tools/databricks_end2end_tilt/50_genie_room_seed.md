### Genie room: “Tilt Site01 Operations” (seed prompts + questions)

Use this file to seed a Genie space / room. The goal is to demonstrate business value: “what happened, why, and what to do.”

## Suggested room context (paste into Genie instructions)

You are an operations analyst assistant for Tilt Renewables “Site01” (demo). You have access to Silver/Gold tables in
catalog `ignition_demo`, schema `tilt_ot`.

Prefer answering with:

- a short explanation (what/why),
- a query-backed number,
- and a recommended next action.

Use these key views:

- Gold KPIs: `gold_site_kpis_5m`, `gold_site_kpis_daily`, `gold_dispatch_performance_5m`, `gold_forecast_accuracy_hourly`,
  `gold_asset_reliability_daily`, `gold_revenue_proxy_daily`
- Silver drilldowns: `silver_signals_1m`, `silver_signals_latest`, `silver_grid_events`, `silver_maintenance_events`

## Demo questions (high-signal)

- “Why is Site01 export below target right now?”
- “How much curtailment did we have in the last 2 hours? Was there an active constraint?”
- “What’s our dispatch tracking MAE today? Show it by hour.”
- “Did BESS reduce tracking error during constraints? Compare intervals with constraint_active=true vs false.”
- “What’s the current SoC and what mode is BESS effectively in (charging/discharging)?”
- “Which asset had the most forced outage time in the last 7 days?”
- “How many active work orders do we have, and are any high priority?”
- “How accurate is the next-hour net forecast today vs yesterday?”
- “Estimate the revenue impact of curtailment today using price proxy.”

## ‘Show me’ drilldowns

- “Show me the last 6 hours of export vs target with curtailment% and price on the same timeline.”
- “List the timestamps where voltage sag or frequency event occurred today and what export power was at those times.”
- “For each turbine (T01/T02/T03), show power trend and forced_outage flag over the last day.”



