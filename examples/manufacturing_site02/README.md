## Manufacturing “Glass Line” simulation (Ignition) — business demo

This demo is modeled after a **glass manufacturing line** (furnace → forming → conveyor → cutting) and is designed to tell a full “OT → Lakehouse → AI/BI” business story:

- Local plant OT equipment → Local Ignition
- OT/IT boundary (firewall/VPN/PrivateLink)
- Central Databricks lakehouse (Bronze → Silver → Gold)
- Multiple downstream consumers (BI, SAP, APIs)

The point of the demo is to show:

- **Operational outcomes**: “throughput vs target”, “scrap/quality improving”, “maintenance impact”
- **Data engineering outcomes**: raw tag events → normalized signals → KPIs
- **Analytics outcomes**: dashboards + Genie questions that map to plant outcomes

### Flow (pictorial)

```text
Ignition Gateway (tags + timer scripts)
  [manufacturing]          plant telemetry (furnace + conveyor + cutting + KPIs)
  [manufacturing_grid]     dispatch / constraints + energy context
  [manufacturing_cmms]     maintenance / work orders
  [manufacturing_forecast] next-hour throughput + scrap forecast
        |
        v
Zerobus Connector (explicit tag paths)
        |
        v
Databricks Lakehouse
  Bronze: ignition_demo.scada_data.tag_events
        |
        v
  Silver: ignition_demo.saint_ot (mapping + normalized views)
        |
        v
  Gold: ignition_demo.saint_ot (KPIs, rollups, forecast accuracy)
        |
        +--> Dashboards (AI/BI)
        |
        +--> Genie (Q&A on Gold + drilldown to Silver)
```

### What do “grid”, “cmms”, and “forecast” mean for a manufacturing site?

In a real Manufacturing environment, data doesn’t just come from PLC/SCADA tags. This demo splits signals into 4 logical “source systems” to reflect how OT data is typically used:

- **`manufacturing` (plant telemetry)**: real-time process + equipment signals from PLC/SCADA.
- **`manufacturing_grid` (constraints + energy context)**: production schedule/dispatch signals and “external context” that affects decisions (energy price spikes, line constraints). It’s not “wind curtailment”; it’s **production throttling / constraints** expressed as a percentage.
- **`manufacturing_cmms` (maintenance / EAM / CMMS)**: work orders + outage flags and health indicators (often SAP PM / Maximo / ServiceNow / in-house systems).
- **`manufacturing_forecast` (near-term prediction)**: a lightweight “what do we expect in the next hour?” feed (could come from a data science model). For manufacturing, forecasting **throughput** and **scrap** is often more relevant than “weather”.

The key idea: **multiple sources drive the plant outcome**, and Databricks can unify them for analytics and AI.

### Provider names (recommended)

Use **separate providers per customer** so you can share a single Bronze table and still keep mapping clean:

- `manufacturing` (plant telemetry)
- `manufacturing_grid` (grid/dispatch inputs)
- `manufacturing_cmms` (maintenance/work orders)
- `manufacturing_forecast` (forecast)

> These can run alongside the renewables demo on the same host.

### What’s included

Import JSON exports into the corresponding providers:

- `manufacturing_site02_tags.json` → provider `manufacturing`
- `manufacturing_grid_site01_tags.json` → provider `manufacturing_grid`
- `manufacturing_cmms_site01_tags.json` → provider `manufacturing_cmms`
- `manufacturing_forecast_site01_tags.json` → provider `manufacturing_forecast`

Gateway Timer Scripts (top-level scripts; paste as-is):

- `timer_script_manufacturing_site02_plant.py` (1s)
- `timer_script_manufacturing_site02_grid.py` (1s)
- `timer_script_manufacturing_site02_cmms.py` (2s)
- `timer_script_manufacturing_site02_forecast.py` (5s)

Each provider has `Diagnostics/*` tags:

- `TickCount` increments when the script runs
- `LastRun/LastStatus/LastError` are quick “self-debug” signals

### Demo tag model (glass production line)

`[manufacturing]Manufacturing/Site02/...`

- Furnace (melting/forming temps, pressure, gas flow)
- Conveyor (speed, load, vibration)
- Cutting station (cut count, blade temp, quality score)
- KPIs (line throughput, scrap rate proxy)

`[manufacturing_grid]Manufacturing/Site02/...`

- Dispatch inputs: `TargetRate_units_per_min`, `Curtailment_pct`, `ConstraintActive`
- Energy context (for cost story): `GasPrice_EUR_per_GJ`, `ElectricityPrice_EUR_per_MWh`
- Events: `EnergySpikeActive`, `LastEvent`

`[manufacturing_cmms]Manufacturing/Site02/...`

- Work order counts + forced outage flags per asset (furnace/conveyor/cutting)

`[manufacturing_forecast]Manufacturing/Site02/...`

- Next-hour forecast of **throughput + scrap** with a confidence %

### Key tags (what they mean)

Below are the main “business story” tags and how to explain them during a demo.

#### `manufacturing` (plant telemetry) — process + equipment

- **`[manufacturing]Manufacturing/Site02/Config/SimEnabled`**: kill-switch for the simulator (true/false).
- **`[manufacturing]Manufacturing/Site02/Config/UpdateEveryMs`**: throttle simulation updates (default 1000ms).
- **Furnace**:
  - **`Temperature_Melting_C`**: melt zone temperature (\~900–1650°C)
  - **`Temperature_Forming_C`**: forming zone temperature (\~750–1250°C)
  - **`Pressure_Chamber_bar`**: furnace chamber pressure (\~0.85–1.25 bar)
  - **`Gas_Flow_m3h`**: fuel gas flow rate (proxy for energy intensity)
  - **`Glass_Thickness_mm`**: product thickness control variable (drives quality)
- **Conveyor**:
  - **`Speed_mpm`**: conveyor speed (m/min)
  - **`Load_kg`**: estimated load on the conveyor (proxy for mechanical stress)
  - **`Vibration_mms`**: vibration (mm/s). This is the classic “predictive maintenance” signal.
- **Cutting station**:
  - **`Cut_Count`**: cumulative count of cuts produced
  - **`Blade_Temp_C`**: blade temperature (proxy for wear/overheating)
  - **`Quality_Score`**: 0–100 score (higher is better), affected by thickness drift + vibration + furnace stability
- **KPIs**:
  - **`Throughput_units_per_min`**: actual line output rate
  - **`ScrapRate_pct`**: scrap proxy % (higher is worse)

#### `manufacturing_grid` (constraints + energy context) — schedule + “why we throttle”

These tags represent what production planning / energy context might send to OT:

- **`TargetRate_units_per_min`**: desired production rate (setpoint / plan)
- **`Curtailment_pct`**: “throttle %” applied when constrained (0–50%). In manufacturing, interpret this as **rate reduction due to constraints** (quality, maintenance, energy spike, downstream blockage).
- **`ConstraintActive`**: boolean “we are constrained right now”
- **Energy context (optional story)**:
  - **`GasPrice_EUR_per_GJ`**
  - **`ElectricityPrice_EUR_per_MWh`**
  - These let you tell a realistic “cost-aware operations” story (price spikes correlate with constraints and shift decisions).
- **Events**:
  - **`EnergySpikeActive`**: boolean “electricity price spike event”
  - **`LastEvent`**: text label such as `ENERGY_SPIKE` / `CONSTRAINT`

In the simulator, `manufacturing_grid` is generated from plant conditions (scrap) and random “market spike” events. In a real site, it might come from energy management, ERP/MES, or grid contracts.

#### `manufacturing_cmms` (maintenance / CMMS) — work orders + outages + health

- **Work order backlog**:
  - **`WorkOrders/ActiveCount`**
  - **`WorkOrders/HighPriorityCount`**
  - **`WorkOrders/LastWorkOrderId`**, **`LastWorkOrderSummary`**
- **Per-asset condition** (`Furnace`, `Conveyor`, `CuttingStation`):
  - **`ForcedOutage`**: boolean “this asset is forced out”
  - **`OutageReason`**: short text reason (preventive/corrective/sensor)
  - **`HealthScore`**: 60–99 (rises when healthy, decays during outages)

In the plant simulator, these outages directly reduce throughput (e.g., conveyor outage forces speed to 0).

#### `manufacturing_forecast` (next-hour) — what the model expects

- **`Forecast/H01/AsOfTime`**: timestamp string for when forecast was produced
- **`Forecast/H01/Throughput_units_per_min`**: expected throughput next hour
- **`Forecast/H01/ScrapRate_pct`**: expected scrap next hour
- **`Forecast/H01/Confidence_pct`**: 35–95% confidence indicator

This is used for the “proactive operations” story: **do we expect problems in the next hour, and why?**

### What to ingest (Zerobus “Explicit Tag Paths”)

You can ingest *folders* if you want, but for demos it’s easiest to use explicit paths so you control scope.
Selection modes for direct subscriptions:

- **Explicit**: subscribe to exactly the tag paths you list.
- **Folder**: browse a folder and subscribe to **all Atomic Tags** under it (optionally include subfolders).
- **Pattern**: browse providers and subscribe to Atomic Tags whose **full tag path** matches a **Java regex**.

Minimum “business story” paths:

- Plant (`manufacturing`)
  - `[manufacturing]Manufacturing/Site02/Furnace/Temperature_Melting_C`
  - `[manufacturing]Manufacturing/Site02/Furnace/Temperature_Forming_C`
  - `[manufacturing]Manufacturing/Site02/Furnace/Pressure_Chamber_bar`
  - `[manufacturing]Manufacturing/Site02/Furnace/Gas_Flow_m3h`
  - `[manufacturing]Manufacturing/Site02/Furnace/Glass_Thickness_mm`
  - `[manufacturing]Manufacturing/Site02/Conveyor/Speed_mpm`
  - `[manufacturing]Manufacturing/Site02/Conveyor/Vibration_mms`
  - `[manufacturing]Manufacturing/Site02/CuttingStation/Quality_Score`
  - `[manufacturing]Manufacturing/Site02/KPIs/Throughput_units_per_min`
  - `[manufacturing]Manufacturing/Site02/KPIs/ScrapRate_pct`

- Grid/dispatch (`manufacturing_grid`)
  - `[manufacturing_grid]Manufacturing/Site02/Dispatch/TargetRate_units_per_min`
  - `[manufacturing_grid]Manufacturing/Site02/Dispatch/Curtailment_pct`
  - `[manufacturing_grid]Manufacturing/Site02/Dispatch/ConstraintActive`
  - `[manufacturing_grid]Manufacturing/Site02/Energy/GasPrice_EUR_per_GJ`
  - `[manufacturing_grid]Manufacturing/Site02/Energy/ElectricityPrice_EUR_per_MWh`
  - `[manufacturing_grid]Manufacturing/Site02/Events/EnergySpikeActive`

- Maintenance (`manufacturing_cmms`)
  - `[manufacturing_cmms]Manufacturing/Site02/WorkOrders/ActiveCount`
  - `[manufacturing_cmms]Manufacturing/Site02/WorkOrders/HighPriorityCount`
  - `[manufacturing_cmms]Manufacturing/Site02/Assets/Furnace/ForcedOutage`
  - `[manufacturing_cmms]Manufacturing/Site02/Assets/Conveyor/ForcedOutage`
  - `[manufacturing_cmms]Manufacturing/Site02/Assets/CuttingStation/ForcedOutage`

- Forecast (`manufacturing_forecast`)
  - `[manufacturing_forecast]Manufacturing/Site02/Forecast/H01/Throughput_units_per_min`
  - `[manufacturing_forecast]Manufacturing/Site02/Forecast/H01/ScrapRate_pct`
  - `[manufacturing_forecast]Manufacturing/Site02/Forecast/H01/Confidence_pct`

Optional debug (don’t need for business story):

- `[manufacturing]Manufacturing/Site02/Diagnostics/TickCount`
- `[manufacturing_grid]Manufacturing/Site02/Diagnostics/TickCount`
- `[manufacturing_cmms]Manufacturing/Site02/Diagnostics/TickCount`
- `[manufacturing_forecast]Manufacturing/Site02/Diagnostics/TickCount`

### Databricks: Bronze → Silver → Gold (Manufacturing schema)

This demo **reuses the same Bronze table** you already have:

- **Bronze**: `ignition_demo.scada_data.tag_events`

and builds Manufacturing layers in a dedicated schema:

- **Silver/Gold**: `ignition_demo.saint_ot`

Run these in order:

- `tools/databricks_end2end_sg/10_silver_scaffolding.sql`
  - Creates `silver_asset_registry`, `silver_signal_mapping`, and view `silver_events_normalized`
- `tools/databricks_end2end_sg/11_seed_site01_mapping.sql`
  - Seeds mapping from **tag_path → asset_id + signal_name + unit + domain**
- `tools/databricks_end2end_sg/20_silver_views.sql`
  - Creates convenience views like `silver_signals_1m`, `silver_signals_latest`, `silver_maintenance_events`
- `tools/databricks_end2end_sg/30_gold_views.sql`
  - Creates KPI views: `gold_site_kpis_5m`, `gold_site_kpis_daily`, `gold_forecast_accuracy_hourly`

Notes:

- These are mostly **views** over Bronze + mapping, so as new Bronze events arrive the Silver/Gold views reflect them automatically.
- If you change tag names, re-run **`11_seed_site01_mapping.sql`** to update mapping.

### Dashboards (suggested)

Use `tools/databricks_end2end_sg/40_dashboard_queries.sql` as a starter set. Recommended dashboards:

- **Operations overview** (last 6h): throughput vs target, scrap %, quality score, curtail/constraint, work orders
- **Energy + cost story (optional)**: energy prices vs constraint vs throughput (cost proxy in daily KPI view)
- **Maintenance impact**: forced outage flags + work order counts vs throughput/scrap
- **Forecast accuracy**: next-hour throughput forecast accuracy trend + confidence

### Genie room (suggested tables + questions)

Use `tools/databricks_end2end_sg/50_genie_room_seed.md`.

Suggested tables/views to add:

- `ignition_demo.saint_ot.gold_site_kpis_5m`
- `ignition_demo.saint_ot.gold_site_kpis_daily`
- `ignition_demo.saint_ot.gold_forecast_accuracy_hourly`
- `ignition_demo.saint_ot.silver_signals_1m` (drilldown)
- `ignition_demo.saint_ot.silver_maintenance_events` (drilldown)

Example questions:

- “Why is throughput below target right now?”
- “Is scrap rate increasing? What changed first: furnace temps, vibration, or quality score?”
- “Are there any forced outages active (furnace/conveyor/cutting)?”
- “How many active work orders do we have, and how many are high priority?”
- “How accurate is the next-hour throughput forecast today?”


