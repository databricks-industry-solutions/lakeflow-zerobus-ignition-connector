### Databricks end-to-end (Tilt Renewables demo): Bronze → Silver → Gold → Dashboards → Genie

This folder contains **copy/paste SQL** you can run in Databricks SQL (or notebooks) to build a business-story demo
on top of the Ignition Zerobus connector.

## Assumptions

- Bronze ingest table exists and is Zerobus-enabled.
  - In your environment, use:
    - Bronze source: `ignition_demo.scada_data.tag_events`

This pack builds Silver/Gold in `ignition_demo.tilt_ot` on top of that Bronze table.

## Run order

1. **Create/verify Silver scaffolding**
   - `10_silver_scaffolding.sql`
2. **Seed mapping for the Site01 demo**
   - `11_seed_site01_mapping.sql`
3. **Create Silver views (normalized + resampled + latest)**
   - `20_silver_views.sql`
4. **Create Gold KPI views**
   - `30_gold_views.sql`
5. **Dashboard query pack**
   - `40_dashboard_queries.sql`
6. **Genie room seed questions**
   - `50_genie_room_seed.md`

## What you get

- Silver:
  - `silver_asset_registry` (table)
  - `silver_signal_mapping` (table)
  - `silver_events_normalized` (view)
  - `silver_signals_1m` (view)
  - `silver_signals_latest` (view)
  - `silver_grid_events` (view)
  - `silver_maintenance_events` (view)

- Gold:
  - `gold_site_kpis_5m` (view)
  - `gold_site_kpis_daily` (view)
  - `gold_dispatch_performance_5m` (view)
  - `gold_forecast_accuracy_hourly` (view)
  - `gold_asset_reliability_daily` (view)
  - `gold_revenue_proxy_daily` (view)


