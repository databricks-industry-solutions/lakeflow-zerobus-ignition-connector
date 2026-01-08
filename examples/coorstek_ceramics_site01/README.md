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

## Suggested Zerobus subscriptions (examples)

- `[coorstek]CoorsTek/Site01/Kiln01/Zones/Zone3_Temp_C`
- `[coorstek]CoorsTek/Site01/Pressing/Press01/PressForce_kN`
- `[coorstek_qc]CoorsTek/Site01/QC/Inspection/Vision01/Yield_pct`
- `[coorstek_mes]CoorsTek/Site01/MES/Orders/GoodCount`
- `[coorstek_maintenance]CoorsTek/Site01/Maintenance/WorkOrders/HighPriorityCount`


