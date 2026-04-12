## End-to-end OT business demo (branch: `end2end_ot`)

This branch adds a **business-story demo** on top of the Ignition Zerobus Connector:

- **Four OT “sources” in Ignition** (`tilt`, `grid`, `cmms`, `forecast`) with timers that simulate realistic operations.
- **Databricks Bronze → Silver → Gold** SQL views that continuously reflect the latest ingest.
- **Dashboards** (AI/BI) + **Genie room** prompts for narrative demoing.

### What changed in this branch (high level)

- **Ignition demo assets**: `examples/tilt_renewables_site01/`
  - Tag exports (import into providers):
    - `tilt_sim_site01_tags.json` → provider `tilt`
    - `grid_sim_site01_tags.json` → provider `grid`
    - `cmms_sim_site01_tags.json` → provider `cmms`
    - `forecast_sim_site01_tags.json` → provider `forecast`
  - Added per-source `Diagnostics/*` tags and scripts update them (tick count, last run, last error).
- **Databricks business layer**: `tools/databricks_end2end_tilt/`
  - Uses **Bronze source**: `ignition_demo.scada_data.tag_events`
  - Builds Silver/Gold in: `ignition_demo.ot`

### Dashboards available (from `tools/databricks_end2end_tilt/40_dashboard_queries.sql`)

Create one dashboard with these pages/sections:

- **Executive Ops Overview**
  - Export vs target (with curtailment + price)
  - Latest tiles (export, target, curtailment, price, SoC, work orders)
- **Dispatch & Grid Compliance**
  - Tracking error heatmap (hour × day)
  - Grid events timeline (constraint/frequency/voltage + curtailment)
- **Asset Performance**
  - Turbine power trends (T01/T02/T03)
  - Solar inverter power + availability
  - BESS SoC + net power
- **Maintenance & Reliability**
  - Work orders trend
  - Forced outage ratio by asset (7d)
- **Forecast & Planning**
  - Forecast vs actual net power (last 6h)
  - Forecast accuracy hourly (7d)

### Genie: what you can ask (seeded in `tools/databricks_end2end_tilt/50_genie_room_seed.md`)

Recommended data sources to add to the Genie space:

- Gold: `ignition_demo.ot.gold_*`
- Silver drilldown: `ignition_demo.ot.silver_signals_1m`, `silver_grid_events`, `silver_maintenance_events`

High-signal demo questions:

- “Why is Site01 export below target right now?”
- “How much curtailment did we have in the last 2 hours? Was there an active constraint?”
- “What’s our dispatch tracking MAE today? Show it by hour.”
- “Which asset had the most forced outage time in the last 7 days?”
- “What’s the current SoC and is BESS charging or discharging?”
- “How accurate is the next-hour net forecast today vs yesterday?”
- “Estimate revenue impact of curtailment today (price proxy).”

### Does Bronze → Gold update continuously?

Yes, because Silver and Gold are implemented primarily as **views** over Bronze + mapping tables.
As long as `ignition_demo.scada_data.tag_events` continues to ingest events, dashboards/Genie reflect new data.

The only things you update manually when you add new tags are:

- `ignition_demo.ot.silver_asset_registry` (table)
- `ignition_demo.ot.silver_signal_mapping` (table)

### “How to tell the business story” (2–3 minute live demo)

In Ignition, force scenarios by writing to a few tags:

- **Curtailment event**: set `[grid]Tilt/Site01/Dispatch/Curtailment_pct` to `30`
- **Price spike**: set `[grid]Tilt/Site01/Market/RRP_AUD_per_MWh` to `300`
- **Forced outage**: set `[cmms]Tilt/Site01/Assets/Windfarm01/T01/ForcedOutage` to `true`

Then show in Databricks:

- Dashboard: export vs target gap, curtailment %, work orders, SoC response
- Genie: ask “why” and “impact” questions above and drill into 1-minute signals


