# AGL Tomago Genie Room – Setup Summary

## Status: Room Created (Data Sources Need Manual Add)

**Room created successfully** via Databricks CLI. Data sources must be added manually in the Genie UI due to an API validation issue with the `agl_ignition` catalog.

---

## Room Details

| Field | Value |
|-------|-------|
| **Title** | AGL Tomago Battery Operations |
| **Description** | Asset intelligence for AGL's Tomago BESS (500MW/2000MWh): real-time KPIs, dispatch performance, reliability, and revenue proxy. Ask questions in natural language. |
| **Space ID** | `01f107039f2e19b5a7c9fb17997bfe3e` |
| **Warehouse** | `862f1d757f0424f7` |
| **Workspace** | https://e2-demo-field-eng.cloud.databricks.com |

---

## Room URL

**https://e2-demo-field-eng.cloud.databricks.com/genie/#/spaces/01f107039f2e19b5a7c9fb17997bfe3e**

---

## Manual Step: Add Data Sources

The Genie API rejected adding tables from `agl_ignition.ot` with:

> Catalog 'agl_ignition.ot.gold_site_kpis_5m' does not exist

Add these tables manually in the Genie room settings:

1. Open the room: https://e2-demo-field-eng.cloud.databricks.com/genie/#/spaces/01f107039f2e19b5a7c9fb17997bfe3e  
2. Click **Settings** (gear icon) → **Data sources**  
3. Add these tables/views:

   - `agl_ignition.ot.gold_site_kpis_5m`
   - `agl_ignition.ot.gold_site_kpis_daily`
   - `agl_ignition.ot.gold_dispatch_performance_5m`
   - `agl_ignition.ot.gold_asset_reliability_daily`
   - `agl_ignition.ot.gold_revenue_proxy_daily`
   - `agl_ignition.ot.silver_signals_latest`
   - `agl_ignition.ot.silver_signals_1m`
   - `agl_ignition.ot.silver_grid_events`
   - `agl_ignition.ot.silver_maintenance_events`

---

## Room Instructions (Already Applied)

The following context from `50_genie_room_seed.md` is already in the room:

```
You are an asset intelligence assistant for AGL's Tomago Battery (NSW) demo.
Use Gold views for summaries and KPI trends, and Silver views for drilldown.

Primary catalog: agl_ignition
Primary schema: ot

Gold views:
- gold_site_kpis_5m
- gold_site_kpis_daily
- gold_dispatch_performance_5m
- gold_asset_reliability_daily
- gold_revenue_proxy_daily

Silver views:
- silver_events_normalized
- silver_signals_1m
- silver_signals_latest
- silver_grid_events
- silver_maintenance_events

When answering:
- state the time window
- include at least one query-backed metric
- give a recommended next action (ops, maintenance, market)
```

---

## Sample Questions (Already Applied)

- What is the current SoC and what is the battery doing (charging/discharging)?
- Are we dispatch-limited, constraint-limited, or thermally derated right now?

Additional questions from `50_genie_room_seed.md` can be added in the room settings.

---

## Blockers / Notes

| Item | Status |
|------|--------|
| **Login** | Assume SSO; workspace accessible via CLI |
| **Permissions** | Creator has CAN MANAGE on the room |
| **Data sources via API** | Failed; add manually (see above) |
| **Possible cause** | Genie warehouse may not have access to `agl_ignition`, or API validation treats the full identifier incorrectly |
