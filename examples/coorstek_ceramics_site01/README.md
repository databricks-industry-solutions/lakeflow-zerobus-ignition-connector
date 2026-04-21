### CoorsTek (USA) — Technical ceramics manufacturing demo (Ignition) — example

This demo models a **technical ceramics** plant with multiple source systems (multiple tag providers) to make the story feel like a real factory:

- **Process / SCADA**: mixing → spray dryer → pressing → kiln/sintering → grinding
- **Quality**: inspection + SPC (yield, defect types, Cpk)
- **MES**: orders + WIP + counts + OEE-ish indicators (no energy)
- **Maintenance**: work orders + condition monitoring + spares

All tags are **Memory tags** so it works without hardware.

## What’s included

Create these 4 tag providers (Standard Tag Providers):

- `coorstek` (process / SCADA)
- `coorstek_qc` (quality)
- `coorstek_mes` (MES)
- `coorstek_maintenance` (maintenance)

Import JSONs:

- Provider `coorstek` → `coorstek_site01_process_tags.json`
- Provider `coorstek_qc` → `coorstek_site01_qc_tags.json`
- Provider `coorstek_mes` → `coorstek_site01_mes_tags.json`
- Provider `coorstek_maintenance` → `coorstek_site01_maintenance_tags.json`

Gateway Timer Scripts (create 4 timers):

- `timer_script_coorstek_site01_process.py` (1000ms)
- `timer_script_coorstek_site01_qc.py` (2000ms)
- `timer_script_coorstek_site01_mes.py` (5000ms)
- `timer_script_coorstek_site01_maintenance.py` (10000ms)

Each provider includes `Diagnostics/*` tags: `TickCount`, `LastRun`, `LastStatus`, `LastError`.

## Important note about timer script style (Ignition 8.1)

On some Ignition 8.1 setups, **Gateway Timer Scripts** can behave like this:
- `system` is available at the **top-level** of the script, but
- top-level variables and `system` may **not** be visible inside `def` functions.

This can cause confusing errors like:
`NameError: global name 'system' is not defined`

### Recommended: use the write-only "NO FUNCTIONS" timers

These scripts are written as **top-level code only (no defs)** and use `system.*` directly.
They are the most reliable “plumbing validation” scripts:

- Process: `timer_script_coorstek_site01_process_write_only.py` (1000ms)
- QC: `timer_script_coorstek_site01_qc_write_only.py` (2000ms)
- MES: `timer_script_coorstek_site01_mes_write_only.py` (5000ms)
- Maintenance: `timer_script_coorstek_site01_maintenance_write_only.py` (10000ms)

Once everything is flowing, you can switch back to the richer model scripts if desired.

## Sanity check (if “numbers aren’t changing”)

### 1) Confirm the tag paths match what the scripts write

The scripts assume the tags exist at these exact paths:

- Process provider: `[coorstek]CoorsTek/Site01/Diagnostics/TickCount`
- QC provider: `[coorstek_qc]CoorsTek/Site01/Diagnostics/TickCount`
- MES provider: `[coorstek_mes]CoorsTek/Site01/Diagnostics/TickCount`
- Maintenance provider: `[coorstek_maintenance]CoorsTek/Site01/Diagnostics/TickCount`

If you imported the JSON **under an extra folder** (e.g. `[coorstek]Demo/CoorsTek/Site01/...`), the scripts won’t find the tags and nothing will update. Import at the **provider root**.

### 2) Confirm the Gateway Timer Events are enabled

Designer → **Scripting → Gateway Events → Timer**

- Ensure each event is **Enabled**
- After saving, watch `Diagnostics/LastRun` update.

### 3) Check `Diagnostics/LastError`

If a script is running but failing, `Diagnostics/LastError` will contain the message.

## Suggested Zerobus subscriptions (examples)

- `[coorstek]CoorsTek/Site01/Kiln01/Zones/Zone3_Temp_C`
- `[coorstek]CoorsTek/Site01/Pressing/Press01/PressForce_kN`
- `[coorstek_qc]CoorsTek/Site01/QC/Inspection/Vision01/Yield_pct`
- `[coorstek_mes]CoorsTek/Site01/MES/Orders/GoodCount`
- `[coorstek_maintenance]CoorsTek/Site01/Maintenance/WorkOrders/HighPriorityCount`


