### Databricks end-to-end (AGL Tomago BESS demo): Bronze → Silver → Gold → Dashboards → Genie

This folder contains **copy/paste SQL** you can run in Databricks SQL (or notebooks) to build a business-story demo
on top of the Ignition Zerobus connector.

## Assumptions

- Catalog: `agl_ignition`
- Bronze ingest table exists and is Zerobus-enabled:
  - `agl_ignition.scada_data.tag_events`

This pack builds Silver/Gold in:

- `agl_ignition.ot`

## Run order

1. **Create/verify Silver scaffolding**
   - `10_silver_scaffolding.sql`
2. **Seed mapping for the Tomago Site01 demo**
   - `11_seed_tomago_site01_mapping.sql`
3. **Create Silver views (normalized + resampled + latest + event views)**
   - `20_silver_views.sql`
4. **Create Gold KPI views**
   - `30_gold_views.sql`
5. **Dashboard query pack**
   - `40_dashboard_queries.sql`
6. **Genie room seed questions**
   - `50_genie_room_seed.md`

