### AGL Energy — Tomago Battery (NSW) — BESS demo tag model (Ignition) — example

This example is a **grid-scale Battery Energy Storage System (BESS)** demo inspired by AGL's Tomago Battery project:

- **500 MW / 2,000 MWh** (4-hour duration)
- **Tomago, New South Wales (Australia)**
- Delivery partner: **Fluence** (Gridstack Pro)

The intent is a leadership-friendly Asset Intelligence story:

- "What is the battery doing right now (SoC / charge / discharge)?"
- "Are we dispatch-limited, constraint-limited, or thermally derated?"
- "Is performance limited by maintenance or alarms?"
- "What's the (proxy) revenue impact of constraints vs price?"

---

## Data flow overview

```
Ignition Gateway           Zerobus Connector           Delta Lake              Demo App
─────────────────         ─────────────────          ────────────           ──────────
                           (module installed)
Timer Scripts ──────┐
  update memory tags │     ┌───────────────┐     ┌──────────────────┐
                     ├────►│ Tag Subscriptions │────►│ agl_ignition.      │
Tag Providers ───────┘     │ → Protobuf stream │     │ scada_data.        │
  agl_bess                 │ → gRPC to Zerobus │     │ tag_events         │
  agl_grid                 └───────────────┘     │                        │
  agl_market                                      │ (bronze)              │
  agl_cmms                                        └──────────┬───────────┘
                                                             │
                                                             ▼
                                                  ┌──────────────────────┐
                                                  │ silver_signal_mapping│
                                                  │ silver_events_normal │
                                                  │ (silver views)       │
                                                  └──────────┬───────────┘
                                                             │
                                                             ▼
                                                  ┌──────────────────────┐
                                                  │ Gold views for       │
                                                  │ dashboards / apps    │
                                                  └──────────────────────┘
```

---

## What's included (4 providers → multi-system narrative)

Create these **Standard Tag Providers** in Ignition:

| Provider | Description | JSON File | Timer Script Rate |
|----------|-------------|-----------|-------------------|
| `agl_bess` | BESS telemetry: PCS/BMS/HVAC | `agl_bess_tomago_site01_tags.json` | 1s |
| `agl_grid` | POI metering + dispatch/constraints | `agl_grid_tomago_site01_tags.json` | 1s |
| `agl_market` | NEM price + FCAS flags | `agl_market_tomago_site01_tags.json` | 2s |
| `agl_cmms` | Maintenance/work orders | `agl_cmms_tomago_site01_tags.json` | 10s |

---

## Quick start options

### Option A: Automation script (recommended)

Use the Python script to automate tag setup:

```bash
cd examples/agl_tomago_bess_site01

# Dry run - see what would be done
python push_tags_to_ignition.py --gateway http://localhost:8088 --dry-run

# Execute (requires Web Dev module)
python push_tags_to_ignition.py --gateway http://localhost:8088 \
    --user admin --password <gateway_password>
```

The script guides you through provider creation, tag import, and timer script setup.

### Option B: Manual setup in Ignition Designer

---

## Ignition Designer setup (step-by-step)

### Step 1: Create tag providers

1. Open Ignition Designer and connect to your Gateway
2. Go to **Config → OPC-UA → Device Connections** (or just use memory tags)
3. For each provider, create a new **Standard Tag Provider**:
   - Name: `agl_bess` (and similarly for `agl_grid`, `agl_market`, `agl_cmms`)

### Step 2: Import tag JSON files

1. In Ignition Designer, open the **Tag Browser** panel
2. Right-click on the target provider (e.g., `agl_bess`)
3. Select **Import Tags...**
4. Browse to this directory and select the corresponding JSON file:
   - `agl_bess_tomago_site01_tags.json` for `agl_bess` provider
   - `agl_grid_tomago_site01_tags.json` for `agl_grid` provider
   - `agl_market_tomago_site01_tags.json` for `agl_market` provider
   - `agl_cmms_tomago_site01_tags.json` for `agl_cmms` provider
5. Click **Import** - the folder structure `AGL/Australia/NSW/Tomago/Site01/...` will be created

### Step 3: Create timer scripts

The timer scripts simulate realistic tag value changes. To create them:

1. Go to **Config → Gateway Events → Timer Scripts**
2. Click **Create new Timer Script**
3. For each script:

| Script Name | Rate | Python File |
|-------------|------|-------------|
| `agl_bess_tomago_sim` | 1000ms | `timer_script_agl_bess_tomago_site01.py` |
| `agl_grid_tomago_sim` | 1000ms | `timer_script_agl_grid_tomago_site01.py` |
| `agl_market_tomago_sim` | 2000ms | `timer_script_agl_market_tomago_site01.py` |
| `agl_cmms_tomago_sim` | 10000ms | `timer_script_agl_cmms_tomago_site01.py` |

4. Copy the entire content of each `.py` file into the script editor
5. Enable each timer script

### Step 4: Verify simulation is running

Check the `Diagnostics/TickCount` tag in each provider - it should increment on each timer tick. If `Config/SimEnabled` is `true`, the simulation is active.

---

## Zerobus connector configuration

To stream the simulated tags to Databricks:

1. **Install the Zerobus module** on your Ignition Gateway (see `/releases/` for `.modl` files)
2. **Configure connection settings**:
   - Zerobus Endpoint (Azure: `australiaeast` region)
   - OAuth Client ID / Secret (from Databricks)
   - Target Delta table: `agl_ignition.scada_data.tag_events`
3. **Subscribe to tag providers**:
   - Add providers `agl_bess`, `agl_grid`, `agl_market`, `agl_cmms` to the subscription list
   - Or use tag path patterns like `[agl_*]AGL/Australia/NSW/Tomago/**`

The connector will:
- Listen for tag change events
- Apply SDT compression (configurable)
- Stream to Zerobus via gRPC/protobuf
- Data lands in your Delta table

---

## Schema compatibility

### Bronze layer (Zerobus output)

The Zerobus connector outputs to `agl_ignition.scada_data.tag_events` with this schema:

| Column | Type | Example |
|--------|------|---------|
| `event_id` | STRING | UUID |
| `event_time` | TIMESTAMP | 2026-02-13 10:30:45.123 |
| `tag_path` | STRING | `[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/SoC_pct` |
| `tag_provider` | STRING | `agl_bess` |
| `numeric_value` | DOUBLE | 52.3 |
| `string_value` | STRING | (for string tags) |
| `boolean_value` | BOOLEAN | (for boolean tags) |
| `quality` | STRING | `GOOD` |
| `source_system` | STRING | `ignition_gateway_01` |

### Silver layer (normalized view)

The SQL in `pipelines/sites/agl_tomago/` provides:

- **`silver_signal_mapping`** - maps `tag_path` → `asset_id`, `signal_name`, `unit`
- **`silver_events_normalized`** - join of bronze + mapping for analytics

This view provides:
- `asset_id` (e.g., `bess01`, `substation01`)
- `signal_name` (e.g., `soc_pct`, `poi_export_mw`)
- `value_numeric` (scaled/offset-adjusted)
- `source_domain` (e.g., `bess`, `grid`, `market`, `cmms`)

### Running the SQL setup

```bash
# From Databricks SQL Editor or CLI:
# 1. Create schemas + tables
databricks sql exec -f pipelines/sites/agl_tomago/10_silver_scaffolding.sql

# 2. Seed asset registry + signal mappings
databricks sql exec -f pipelines/sites/agl_tomago/11_seed_tomago_site01_mapping.sql

# 3. Create silver/gold views
databricks sql exec -f pipelines/sites/agl_tomago/20_silver_views.sql
databricks sql exec -f pipelines/sites/agl_tomago/30_gold_views.sql
```

---

## Tag path convention

All paths follow:

`[provider]AGL/Australia/NSW/Tomago/Site01/...`

Examples:

| Tag Path | Signal Mapping |
|----------|----------------|
| `[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/SoC_pct` | `bess01.soc_pct` |
| `[agl_grid]AGL/Australia/NSW/Tomago/Site01/Substation01/POI/ExportPower_MW` | `substation01.poi_export_mw` |
| `[agl_market]AGL/Australia/NSW/Tomago/Site01/Market/RRP_AUD_per_MWh` | `market.rrp_aud_per_mwh` |
| `[agl_cmms]AGL/Australia/NSW/Tomago/Site01/CMMS/OpenWorkOrders` | `cmms.open_work_orders` |

---

## Diagnostics tags

Each provider includes `Diagnostics/*` tags:

- `TickCount` - increments on each script tick
- `LastRun` - timestamp of last execution
- `LastStatus` - "tick ok" or error message
- `LastError` - detailed error if any

---

---

## Using with demo app (PRD schema bridge)

The demo app (`demo/app/`) expects data in the PRD schema (`raw_tags` with `asset_id`, `tag_name`, `tag_value`). The Ignition connector outputs a different schema.

To bridge this gap, run the bridge view SQL:

```bash
databricks sql exec -f pipelines/sites/agl_tomago/25_bridge_to_prd_schema.sql
```

This creates `agl_ignition.agl_demo_compat.raw_tags` which maps the silver events to PRD format.

**Option 1: Update demo app to query bridge views**

In `demo/app/backend/services/query.py`, change table references:
- `FROM raw_tags` → `FROM agl_ignition.agl_demo_compat.raw_tags`
- `FROM assets` → `FROM agl_ignition.agl_demo_compat.assets`

**Option 2: Create catalog aliases**

```sql
-- In agl_demo catalog, create aliases to bridge views
CREATE OR REPLACE VIEW agl_demo.ot.raw_tags AS
SELECT * FROM agl_ignition.agl_demo_compat.raw_tags;

CREATE OR REPLACE VIEW agl_demo.ot.assets AS
SELECT * FROM agl_ignition.agl_demo_compat.assets;
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Tags not updating | Check `Config/SimEnabled` is `true` |
| Timer script errors | Check `Diagnostics/LastError` for details |
| No data in Delta | Verify Zerobus connector is connected and subscribed |
| Missing mappings | Run `11_seed_tomago_site01_mapping.sql` to populate signal mappings |
| Demo app shows no data | Run `25_bridge_to_prd_schema.sql` and update table references |
| Push script fails | Ensure Ignition Web Dev module is installed and enabled |

