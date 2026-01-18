### OilGas (Region) — Oil & Gas demo tag model (Ignition) — example

This folder contains a lightweight **Ignition 8.1** demo designed to feel like a real upstream + surface facility data flow.

## Story / flow (what this demo is showing)

```text
Ignition (Gateway tags + timer scripts)
  [oil_gas]  pads/wells + surface processing + tanks/flare + safety/integrity
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

- `oil_gas` (SCADA / process)
- `oil_gas_safety` (safety)
- `oil_gas_integrity` (asset integrity)

Import JSONs:

- Provider `oil_gas` → `oil_gas_site01_tags.json`
- Provider `oil_gas_safety` → `oil_gas_site01_safety_tags.json`
- Provider `oil_gas_integrity` → `oil_gas_site01_integrity_tags.json`

Gateway Timer Scripts:

- `timer_script_oil_gas_site01.py` (SCADA/process, 1000ms)
- `timer_script_oil_gas_site01_safety.py` (safety baseline, 2000ms)
- `timer_script_oil_gas_site01_integrity.py` (integrity baseline, 10000ms)
- `timer_script_oil_gas_site01_upsets.py` (optional upsets, 5000–10000ms)

## Recommended "write-only / no-functions" timers (Ignition 8.1)

On some Ignition 8.1 timer-script contexts, `system` and other top-level names can be
inconsistent inside `def` functions, causing errors like:
`NameError: global name 'system' is not defined`.

These **write-only** scripts are intentionally written as **top-level code only**
(no defs) and use `system.*` directly, plus Diagnostics-style “tick ok …” logs:

- `timer_script_oil_gas_site01_write_only.py` (process, 1000ms)
- `timer_script_oil_gas_site01_safety_write_only.py` (safety, 2000ms)
- `timer_script_oil_gas_site01_integrity_write_only.py` (integrity, 10000ms)

## What data is modeled (and why it’s relevant)

### Wells / pads (production + well health)

Paths like:

- `[oil_gas]OilGas/Site01/Wells/PadA/W01/Wellhead/*`
- `[oil_gas]OilGas/Site01/Wells/PadA/W01/Production/*`

Key signals:

- **`Wellhead/Pressure_bar`**, **`Temperature_C`**: early indicator of restrictions, choke changes, and surface constraints.
- **`Production/LiquidRate_m3_d`**, **`GasRate_kSm3_d`**: production allocation inputs and short-term production monitoring.
- **`Production/WaterCut_pct`**, **`SandRate_kg_h`**: lift/flow assurance and erosion risk narrative.
- **`Choke_pct`**, **`Enabled`**: “operator action / well status” context that makes analytics explainable.

### Processing (separator + heater + compressor + export)

Paths like:

- `[oil_gas]OilGas/Site01/Processing/Separator01/*`
- `[oil_gas]OilGas/Site01/Processing/Compressor01/*`

Key signals:

- **Separator**: `Pressure_bar`, `Temperature_C`, `Level_pct`, `DP_bar` (stability, capacity, carryover narrative).
- **Heater**: inlet/outlet temperatures and `FuelGas_kSm3_d` (process conditioning narrative).
- **Compressor**: `SuctionPressure_bar`, `DischargePressure_bar`, `Speed_RPM`, `Vibration_mm_s`, `BearingTemp_C` (condition monitoring + trip precursors).
- **Export**: `HeaderPressure_bar`, `ExportFlow_m3_h` (surface constraint narrative).

### Storage / flare (inventory + emissions narrative hooks)

Paths like:

- `[oil_gas]OilGas/Site01/Tanks/Tank01/Level_pct`
- `[oil_gas]OilGas/Site01/Flare/FlareRate_kSm3_h`

Key signals:

- **Tanks**: `Level_pct`, `WaterBottom_pct`, temperature (inventory + offtake timing story).
- **Flare**: flare rate + smokeless assist (upset response and emissions narrative).

### Safety + integrity (events that matter operationally)

Paths like:

- `[oil_gas]OilGas/Site01/Safety/*`
- `[oil_gas]OilGas/Site01/Integrity/*`

Key signals:

- **Safety**: `ESD_Active`, `FireGas_Alarm`, `H2S_ppm` (incident timeline / response narrative).
- **Integrity**: corrosion rate, pigging days, leak suspected (asset integrity story).

### 1) Create the tag providers

In the Gateway UI:

- Go to **Configure → Tags → Realtime Tag Providers**
- Create **three** **Standard Tag Providers** named:
  - `oil_gas`
  - `oil_gas_safety`
  - `oil_gas_integrity`
- Ensure each is **Enabled** and **NOT Read Only**

> Provider names must match exactly; the JSON exports assume `[oil_gas]...`, `[oil_gas_safety]...`, and `[oil_gas_integrity]...`.

### 2) Import the tags (3 JSON files)

In the Designer connected to the same gateway:

- Open the **Tag Browser**
- Select provider **`oil_gas`**
- Right-click → **Import**
- Choose **JSON**
- Import `examples/oil_gas_site01/oil_gas_site01_tags.json`

Repeat for:

- Provider **`oil_gas_safety`** → import `oil_gas_site01_safety_tags.json`
- Provider **`oil_gas_integrity`** → import `oil_gas_site01_integrity_tags.json`

You should now see:

- `[oil_gas]OilGas/Site01/...`
- `[oil_gas_safety]OilGas/Site01/Safety/...`
- `[oil_gas_integrity]OilGas/Site01/Integrity/...`

### 3) Configure Zerobus connector (optional)

In Zerobus connector config, add a few explicit tag paths (examples):

- `[oil_gas]OilGas/Site01/Wells/PadA/W01/Wellhead/Pressure_bar`
- `[oil_gas]OilGas/Site01/Processing/Separator01/Level_pct`
- `[oil_gas]OilGas/Site01/Tanks/Tank01/Level_pct`
- `[oil_gas]OilGas/Site01/Flare/FlareRate_kSm3_h`
- `[oil_gas_safety]OilGas/Site01/Safety/H2S_ppm`
- `[oil_gas_integrity]OilGas/Site01/Integrity/CorrosionRate_mm_per_yr`

Then verify:

- `GET /system/zerobus/diagnostics` shows `Direct Subscriptions: <N> tags`
- Your target table receives rows with `tag_provider = 'oil_gas'`

### Option: use Folder mode (recommended for customer demos / isolation)

If you don’t want to hand-pick explicit tags—and you want to avoid accidentally selecting other customers’ namespaces—use **Folder** selection mode and subscribe only to the customer’s root folders.

Recommended roots (select the folder and set **Include subfolders = true**):

- **SCADA / process** (provider `oil_gas`):
  - `[oil_gas]OilGas/Site01`
- **Safety** (provider `oil_gas_safety`):
  - `[oil_gas_safety]OilGas/Site01`
- **Integrity** (provider `oil_gas_integrity`):
  - `[oil_gas_integrity]OilGas/Site01`

This keeps the connector scoped to only OilGas’s demo tags (no explicit paths list needed).

### Option: use Pattern mode (single regex, multiple providers)

If you prefer a single **regex** (instead of a single folder root), set Zerobus config:

- **Selection Mode**: `pattern`
- **Tag Path Pattern**: (Java regex; matches the **full tag path string**, including the provider in brackets)

Recommended regex for **OilGas Process + Safety + Integrity**:

```
^\[(oil_gas|oil_gas_safety|oil_gas_integrity)\]OilGas/Site01(/.*)?$
```

Notes:
- This uses Java `Pattern.matcher(fullPath).matches()` semantics (full-string match), so include `^` and `$`.
- The provider brackets are **literal** `[` and `]` in the tag path, so the regex must escape them as `\[` and `\]`.

### 4) Add the Gateway Timer Script (simulator)

In the Designer:

- Go to **Scripting → Gateway Events → Timer**
- Create a timer event (or edit an existing one)
- Set:
  - **Delay Type**: Fixed Delay
  - **Delay (ms)**: 1000
  - **Enabled**: true
- Create a timer (1000ms) and paste `timer_script_oil_gas_site01.py` (SCADA/process).

Then create:

- A timer (2000ms) for `timer_script_oil_gas_site01_safety.py`
- A timer (10000ms) for `timer_script_oil_gas_site01_integrity.py`

Optional (recommended for demos):

- Create a **second** timer event with:
  - **Delay (ms)**: 5000 (or 10000)
  - **Enabled**: true
- Paste `examples/oil_gas_site01/timer_script_oil_gas_site01_upsets.py` (this writes to both `oil_gas` and `oil_gas_safety`)

You should see these tags change about once per second:

- `[oil_gas]OilGas/Site01/Processing/Separator01/Level_pct`
- `[oil_gas]OilGas/Site01/Processing/Compressor01/DischargePressure_bar`
- `[oil_gas]OilGas/Site01/Tanks/Tank01/Level_pct`

### Suggested “wow” demo moments (what to point at live)

- **Compressor trip**: `Compressor01/Running` flips false, vibration/bearing temperature spikes (then settles).
- **Tank high-high**: `Tanks/Tank01/Level_pct` jumps near full; show how quickly the event appears downstream.
- **Safety spike**: `Safety/H2S_ppm` spikes; `FireGas_Alarm` may latch briefly.
- **ESD drill**: `Safety/ESD_Active` true → compressor forced off → flare increases.


