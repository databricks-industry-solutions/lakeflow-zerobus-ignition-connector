## Databricks end-to-end (Saint-Gobain demo): Bronze → Silver → Gold → Dashboards → Genie

This pack reuses the **same Bronze** table as other demos:

- **Bronze source**: `ignition_demo.scada_data.tag_events`

and builds Saint-Gobain specific business layers in:

- **Silver/Gold schema**: `ignition_demo.saint_ot`

### Run order

1. `10_silver_scaffolding.sql`
2. `11_seed_site01_mapping.sql`
3. `20_silver_views.sql`
4. `30_gold_views.sql`
5. `40_dashboard_queries.sql`
6. `50_genie_room_seed.md`


