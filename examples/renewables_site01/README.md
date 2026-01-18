### Renewables “Site01” simulation (Ignition) — end-to-end OT demo

This example is a richer, **multi-asset** Renewables demo (not just wind). It is designed to showcase:

- **Ingest** (Ignition → Databricks Zerobus → Bronze table)
- **Silver** (normalized, typed time series + dimensions)
- **Gold** (KPIs and operations analytics)
- **Dashboards** (AI/BI dashboards in Databricks)
- **Genie** (natural-language questions against Gold/Silver)

This demo uses **Memory tags** + **Gateway Timer Scripts** (Jython) so it works without external hardware.

## Flow (pictorial)

```text
Ignition Gateway (tags + timer scripts)
  [renewables]      plant telemetry (wind + solar + BESS + met mast)
  [grid]      POI + dispatch + market
  [cmms]      maintenance / work orders
  [forecast]  next-hour forecast
        |
        v
Zerobus Connector (explicit tag paths)
        |
        v
Databricks Lakehouse
  Bronze: ignition_demo.scada_data.tag_events
        |
        v
  Silver: mapping + normalized views (signal registry, 1m rollups, latest)
        |
        v
  Gold: KPIs (fleet/site performance, constraints, maintenance impact, forecast accuracy)
        |
        +--> Dashboards (AI/BI)
        |
        +--> Genie (Q&A on Gold + drilldown to Silver)
```

## What’s included

This demo uses **four “sources”** (four tag providers) to make the business story realistic:

- **Plant telemetry SCADA**: `[renewables]...` (Wind + Solar + BESS + Met)
- **Grid + market**: `[grid]...` (POI meter, dispatch target, curtailment, price)
- **Maintenance / CMMS**: `[cmms]...` (forced outage flags, work orders, reasons)
- **Forecast**: `[forecast]...` (next-hour forecasts for wind/solar/net)

Included files:

- **`renewables_sim_site01_tags.json`**: Import into provider **`renewables`**.
- **`grid_sim_site01_tags.json`**: Import into provider **`grid`**.
- **`cmms_sim_site01_tags.json`**: Import into provider **`cmms`**.
- **`forecast_sim_site01_tags.json`**: Import into provider **`forecast`**.

Gateway Timer Scripts (create 4 timers at 1s or 2s):

- **`timer_script_site01_plant_telemetry.py`**
- **`timer_script_site01_grid_market.py`**
- **`timer_script_site01_maintenance_events.py`**
- **`timer_script_site01_weather_forecast.py`**

Each provider has `Diagnostics/*` tags:

- `TickCount` increments when the script runs
- `LastRun/LastStatus/LastError` are quick “self-debug” signals

## Demo tag model (Renewables multi-asset)

`[renewables]Renewables/Site01/...`

- `Windfarm01` (turbines, site wind, availability)
- `SolarFarm01` (inverters, irradiance coupling)
- `BESS01` (SOC, charge/discharge, limits)
- `MetMast01` (wind speed, direction, irradiance)

`[grid]Renewables/Site01/...`

- `Substation01/POI/*` (export power, frequency)
- `Dispatch/*` (target and curtailment)
- `Market/*` (price + events)

`[cmms]Renewables/Site01/...`

- `WorkOrders/*` + forced outage flags/reasons

`[forecast]Renewables/Site01/...`

- next-hour forecasts for wind/solar/net

## What do “grid”, “cmms”, and “forecast” mean for a renewable site?

Real renewable operators don’t just look at raw SCADA watts. Day-to-day decisions depend on:

- **`renewables` (plant telemetry / SCADA)**: turbine/inverter/BESS/meteorological signals coming from OT systems.
- **`grid` (grid connection + dispatch + market context)**: what the grid/market is asking for and what the point-of-interconnection is actually doing (POI meter, curtailment, price, frequency events).
- **`cmms` (maintenance / work management)**: work order backlog and “forced outage” flags that directly explain underperformance.
- **`forecast` (near-term prediction)**: next-hour expected wind/solar/net production (what operations will plan against).

The demo uses four providers to mimic “multiple source systems” while still landing everything into a **single Bronze table**.

## Key tags (what they mean)

### `renewables` (plant telemetry / SCADA)

Config / knobs:

- **`[renewables]Renewables/Site01/Config/SimEnabled`**: kill-switch for the simulator.
- **`[renewables]Renewables/Site01/Config/UpdateEveryMs`**: throttle update cadence (default 1000ms).
- **Wind/solar/BESS sizing knobs** (used by the simulation): `RatedPower_T0*_kW`, `SolarACCapacity_kW`, `BESS_EnergyCapacity_kWh`, `BESS_MaxCharge_kW`, `BESS_MaxDischarge_kW`.

Met mast (weather that drives production):

- **`MetMast01/WindSpeed_mps`**, **`WindDir_deg`**: primary driver for turbine power.
- **`MetMast01/Irradiance_Wm2`**: primary driver for solar power.
- `AmbientTemp_C`, `Humidity_pct`, `Pressure_hPa`: extra context for dashboards/Genie.

Wind farm:

- **`Windfarm01/Site/Power_Total_kW`**: total wind power.
- **`Windfarm01/Site/Availability_pct`**: availability proxy.
- **`Windfarm01/Site/Curtailment_pct`**: plant-side curtailment proxy (used for explaining reduced output).
- Per turbine (T01/T02/T03): `Electrical/Power_kW`, `ReactivePower_kVAr`, `PowerFactor`, plus status/fault fields.

Solar farm:

- Per inverter: `AC/Power_kW`, `AC/Frequency_Hz`, and `Availability` / `Status`.
- `SolarFarm01/Plant/Power_Total_kW`: total solar power.

BESS:

- **`SoC/StateOfCharge_pct`**, `StateOfHealth_pct`
- **`Power/NetPower_kW`** (positive = discharge, negative = charge), and split charge/discharge powers
- `Energy/Throughput_MWh`, `Energy/Cycles`: useful “battery story” metrics.

### `grid` (POI meter + dispatch + market context)

POI meter (what the grid actually sees):

- **`Substation01/POI/ExportPower_kW`**, `ImportPower_kW`, `NetPower_kW`
- **`Frequency_Hz`**, `Voltage_kV`, `BreakerClosed`: grid event/connection context

Dispatch / constraints (what operations is asked to do):

- **`Dispatch/TargetExport_kW`**: requested export target.
- **`Dispatch/Curtailment_pct`**: curtailment level applied due to constraints.
- **`Dispatch/ConstraintActive`**: boolean “we are constrained right now”.
- **`Dispatch/FCAS_Enabled`**: optional ancillary services flag (for “grid services” story).

Market / events (why constraints happen):

- **`Market/RRP_AUD_per_MWh`**: spot price (demo uses AUD as Renewables is AU/NZ context).
- **`Market/PriceSpikeActive`**, `Events/FrequencyEventActive`, `Events/VoltageSagActive`, `Events/LastEvent`: event narrative hooks for dashboards/Genie.

### `cmms` (maintenance / work management)

These tags are the “why did we underperform?” layer:

- Work orders: **`WorkOrders/ActiveCount`**, **`HighPriorityCount`**, `LastWorkOrderId`, `LastWorkOrderSummary`
- Asset condition (wind turbines, inverters, BESS):
  - **`Assets/.../ForcedOutage`**: boolean “forced out”
  - **`Assets/.../OutageReason`**: text reason
  - **`Assets/.../HealthScore`**: 60–99 health proxy
- Ops flags: `Operations/TechniciansOnSite`, `Operations/WeatherHold` (useful for explaining downtime).

### `forecast` (next-hour expected production)

These tags model the “what do we expect in the next hour?” data feed:

- **`Forecast/H01/AsOfTime`**
- **`Forecast/H01/WindPower_kW`**, `SolarPower_kW`, `BESSPower_kW`, **`NetPower_kW`**
- **`Forecast/H01/ExpectedCurtailment_pct`**
- **`Forecast/H01/Confidence_pct`**

## 1) Create the tag providers

In the Gateway UI:

- Go to **Configure → Tags → Realtime Tag Providers**
- Create **four** **Standard Tag Providers**:
  - `renewables`
  - `grid`
  - `cmms`
  - `forecast`
- Ensure each is **Enabled** and **NOT Read Only**

> The provider names matter because each JSON export assumes you import into the matching provider.

## 2) Import the tags

In the Designer:

- Open **Tag Browser**
- For each provider, select it and import its JSON:
  - Provider `renewables` → import `renewables_sim_site01_tags.json`
  - Provider `grid` → import `grid_sim_site01_tags.json`
  - Provider `cmms` → import `cmms_sim_site01_tags.json`
  - Provider `forecast` → import `forecast_sim_site01_tags.json`

You should see (examples):

- `[renewables]Renewables/Site01/MetMast01/...`
- `[renewables]Renewables/Site01/Windfarm01/...`
- `[renewables]Renewables/Site01/SolarFarm01/...`
- `[renewables]Renewables/Site01/BESS01/...`
- `[grid]Renewables/Site01/Substation01/...`
- `[cmms]Renewables/Site01/...`
- `[forecast]Renewables/Site01/...`

## 3) Add the Gateway Timer Scripts (simulators)

Designer → **Scripting → Gateway Events → Timer**

- Delay Type: **Fixed Delay**
- Delay (ms): **1000**
- Enabled: **true**
- Create 4 timers and paste one script into each:
  - `timer_script_site01_plant_telemetry.py`
  - `timer_script_site01_grid_market.py`
  - `timer_script_site01_maintenance_events.py`
  - `timer_script_site01_weather_forecast.py`

## 4) Ingest (Zerobus module)

For Ignition 8.1, the recommended ingest path is **direct subscriptions** (no Event Stream scripts required).

Tag selection modes supported for direct subscriptions:

- **Explicit**: subscribe to exactly the tag paths you list.
- **Folder**: browse a folder and subscribe to **all Atomic Tags** under it (optionally include subfolders).
- **Pattern**: browse providers and subscribe to Atomic Tags whose **full tag path** matches a **Java regex**.

Start with a small, high-signal list:

- `[renewables]Renewables/Site01/MetMast01/WindSpeed_mps`
- `[renewables]Renewables/Site01/MetMast01/Irradiance_Wm2`
- `[renewables]Renewables/Site01/Windfarm01/Turbines/T01/Electrical/Power_kW`
- `[renewables]Renewables/Site01/SolarFarm01/Inverters/I01/AC/Power_kW`
- `[renewables]Renewables/Site01/BESS01/Power/NetPower_kW`
- `[grid]Renewables/Site01/Substation01/POI/ExportPower_kW`
- `[grid]Renewables/Site01/Substation01/POI/Frequency_Hz`
- `[grid]Renewables/Site01/Dispatch/Curtailment_pct`
- `[cmms]Renewables/Site01/WorkOrders/ActiveCount`
- `[forecast]Renewables/Site01/Forecast/H01/NetPower_kW`

Then validate:

- `GET /system/zerobus/health`
- `GET /system/zerobus/diagnostics`

## 5) Databricks end-to-end (Bronze → Silver → Gold → Dashboards → Genie)

See:

- `tools/databricks_end2end_renewables/README.md`

Recommended run order in Databricks:

- `tools/databricks_end2end_renewables/10_silver_scaffolding.sql`
- `tools/databricks_end2end_renewables/11_seed_site01_mapping.sql`
- `tools/databricks_end2end_renewables/20_silver_views.sql`
- `tools/databricks_end2end_renewables/30_gold_views.sql`
- `tools/databricks_end2end_renewables/40_dashboard_queries.sql`
- `tools/databricks_end2end_renewables/50_genie_room_seed.md`

### Dashboards (suggested)

- **Fleet overview**: wind/solar/BESS/POI power, curtailment, price
- **Constraint story**: dispatch target vs actual vs curtailment, “why did we under-deliver?”
- **BESS ops**: SOC, net power, charge/discharge cycles, limits/alarms
- **Maintenance impact**: forced outages + work orders vs lost production proxy
- **Forecast vs actual**: next-hour forecast accuracy and confidence

### Genie room (suggested tables + questions)

Use `tools/databricks_end2end_renewables/50_genie_room_seed.md`.

Suggested sources to add:

- Gold KPI views (from `tools/databricks_end2end_renewables/30_gold_views.sql`)
- `...silver_signals_1m` / `...silver_signals_latest` (drilldown)

Example questions:

- “What’s driving curtailment right now and how much energy are we spilling?”
- “Show POI export vs wind + solar + BESS net power in the last 6 hours.”
- “Which turbine is underperforming relative to wind speed?”
- “How often did BESS hit charge/discharge limits today?”
- “How accurate is the next-hour net power forecast?”

