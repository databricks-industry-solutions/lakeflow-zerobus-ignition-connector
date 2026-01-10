### Pluspetrol (Argentina) — Oil & Gas demo tag model (Ignition) — example

This folder contains a lightweight **Ignition 8.1** demo designed to feel like a real upstream + surface facility data flow.

## Story / flow (what this demo is showing)

```text
Ignition (Gateway tags + timer scripts)
  [pluspetrol]  pads/wells + surface processing + tanks/flare + safety/integrity
        |
        v
Zerobus Connector (direct subscriptions)
        |
        v
Databricks Delta (bronze time-series events)
  ignition_demo.scada_data.tag_events
```

The intent is to show **how operational telemetry** (wells → separator → compressor → storage) becomes **analytics-ready** in Databricks in near real-time, including the “what happens during upsets” narrative.

### What’s included (3 providers for a more realistic enterprise story)

Create these 3 tag providers (Standard Tag Providers):

- `pluspetrol` (SCADA / process)
- `pluspetrol_safety` (safety)
- `pluspetrol_integrity` (asset integrity)

Import JSONs:

- Provider `pluspetrol` → `pluspetrol_la_calera_tags.json`
- Provider `pluspetrol_safety` → `pluspetrol_la_calera_safety_tags.json`
- Provider `pluspetrol_integrity` → `pluspetrol_la_calera_integrity_tags.json`

Gateway Timer Scripts:

- `timer_script_pluspetrol_la_calera.py` (SCADA/process, 1000ms)
- `timer_script_pluspetrol_la_calera_safety.py` (safety baseline, 2000ms)
- `timer_script_pluspetrol_la_calera_integrity.py` (integrity baseline, 10000ms)
- `timer_script_pluspetrol_la_calera_upsets.py` (optional upsets, 5000–10000ms)

## What data is modeled (and why it’s relevant)

### Wells / pads (production + well health)

Paths like:

- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Wells/PadA/W01/Wellhead/*`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Wells/PadA/W01/Production/*`

Key signals:

- **`Wellhead/Pressure_bar`**, **`Temperature_C`**: early indicator of restrictions, choke changes, and surface constraints.
- **`Production/LiquidRate_m3_d`**, **`GasRate_kSm3_d`**: production allocation inputs and short-term production monitoring.
- **`Production/WaterCut_pct`**, **`SandRate_kg_h`**: lift/flow assurance and erosion risk narrative.
- **`Choke_pct`**, **`Enabled`**: “operator action / well status” context that makes analytics explainable.

### Processing (separator + heater + compressor + export)

Paths like:

- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Processing/Separator01/*`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Processing/Compressor01/*`

Key signals:

- **Separator**: `Pressure_bar`, `Temperature_C`, `Level_pct`, `DP_bar` (stability, capacity, carryover narrative).
- **Heater**: inlet/outlet temperatures and `FuelGas_kSm3_d` (process conditioning narrative).
- **Compressor**: `SuctionPressure_bar`, `DischargePressure_bar`, `Speed_RPM`, `Vibration_mm_s`, `BearingTemp_C` (condition monitoring + trip precursors).
- **Export**: `HeaderPressure_bar`, `ExportFlow_m3_h` (surface constraint narrative).

### Storage / flare (inventory + emissions narrative hooks)

Paths like:

- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Tanks/Tank01/Level_pct`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Flare/FlareRate_kSm3_h`

Key signals:

- **Tanks**: `Level_pct`, `WaterBottom_pct`, temperature (inventory + offtake timing story).
- **Flare**: flare rate + smokeless assist (upset response and emissions narrative).

### Safety + integrity (events that matter operationally)

Paths like:

- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Safety/*`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Integrity/*`

Key signals:

- **Safety**: `ESD_Active`, `FireGas_Alarm`, `H2S_ppm` (incident timeline / response narrative).
- **Integrity**: corrosion rate, pigging days, leak suspected (asset integrity story).

### 1) Create the tag providers

In the Gateway UI:

- Go to **Configure → Tags → Realtime Tag Providers**
- Create **three** **Standard Tag Providers** named:
  - `pluspetrol`
  - `pluspetrol_safety`
  - `pluspetrol_integrity`
- Ensure each is **Enabled** and **NOT Read Only**

> Provider names must match exactly; the JSON exports assume `[pluspetrol]...`, `[pluspetrol_safety]...`, and `[pluspetrol_integrity]...`.

### 2) Import the tags (3 JSON files)

In the Designer connected to the same gateway:

- Open the **Tag Browser**
- Select provider **`pluspetrol`**
- Right-click → **Import**
- Choose **JSON**
- Import `examples/pluspetrol_la_calera/pluspetrol_la_calera_tags.json`

Repeat for:

- Provider **`pluspetrol_safety`** → import `pluspetrol_la_calera_safety_tags.json`
- Provider **`pluspetrol_integrity`** → import `pluspetrol_la_calera_integrity_tags.json`

You should now see:

- `[pluspetrol]Pluspetrol/Argentina/LaCalera/...`
- `[pluspetrol_safety]Pluspetrol/Argentina/LaCalera/Safety/...`
- `[pluspetrol_integrity]Pluspetrol/Argentina/LaCalera/Integrity/...`

### 3) Configure Zerobus connector (optional)

In Zerobus connector config, add a few explicit tag paths (examples):

- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Wells/PadA/W01/Wellhead/Pressure_bar`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Processing/Separator01/Level_pct`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Tanks/Tank01/Level_pct`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Flare/FlareRate_kSm3_h`
- `[pluspetrol_safety]Pluspetrol/Argentina/LaCalera/Safety/H2S_ppm`
- `[pluspetrol_integrity]Pluspetrol/Argentina/LaCalera/Integrity/CorrosionRate_mm_per_yr`

Then verify:

- `GET /system/zerobus/diagnostics` shows `Direct Subscriptions: <N> tags`
- Your target table receives rows with `tag_provider = 'pluspetrol'`

### 4) Add the Gateway Timer Script (simulator)

In the Designer:

- Go to **Scripting → Gateway Events → Timer**
- Create a timer event (or edit an existing one)
- Set:
  - **Delay Type**: Fixed Delay
  - **Delay (ms)**: 1000
  - **Enabled**: true
- Create a timer (1000ms) and paste `timer_script_pluspetrol_la_calera.py` (SCADA/process).

Then create:

- A timer (2000ms) for `timer_script_pluspetrol_la_calera_safety.py`
- A timer (10000ms) for `timer_script_pluspetrol_la_calera_integrity.py`

Optional (recommended for demos):

- Create a **second** timer event with:
  - **Delay (ms)**: 5000 (or 10000)
  - **Enabled**: true
- Paste `examples/pluspetrol_la_calera/timer_script_pluspetrol_la_calera_upsets.py` (this writes to both `pluspetrol` and `pluspetrol_safety`)

You should see these tags change about once per second:

- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Processing/Separator01/Level_pct`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Processing/Compressor01/DischargePressure_bar`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Tanks/Tank01/Level_pct`

### Suggested “wow” demo moments (what to point at live)

- **Compressor trip**: `Compressor01/Running` flips false, vibration/bearing temperature spikes (then settles).
- **Tank high-high**: `Tanks/Tank01/Level_pct` jumps near full; show how quickly the event appears downstream.
- **Safety spike**: `Safety/H2S_ppm` spikes; `FireGas_Alarm` may latch briefly.
- **ESD drill**: `Safety/ESD_Active` true → compressor forced off → flare increases.


