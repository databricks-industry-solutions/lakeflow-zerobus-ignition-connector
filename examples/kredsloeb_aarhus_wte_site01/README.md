## Kredsløb (Aarhus, Denmark) — Waste-to-Energy + District Heating + Emissions demo

This demo models the kind of OT data a municipal utility like **Kredsløb** would have in SCADA:

- **Waste-to-energy** process (furnace/boiler/steam/turbine)
- **District heating network** (supply/return/flow/heat output)
- **Environmental / emissions** (NOx/CO/dust + compliance flags)

### 1) Create Tag Providers (manual)

Create these Ignition Tag Providers first:

- `kredsloeb_process`
- `kredsloeb_dh`
- `kredsloeb_env`

### 2) Import tags

Import each JSON at the provider root:

- Provider `[kredsloeb_process]` → `kredsloeb_process_aarhus_site01_tags.json`
- Provider `[kredsloeb_dh]` → `kredsloeb_dh_aarhus_site01_tags.json`
- Provider `[kredsloeb_env]` → `kredsloeb_env_aarhus_site01_tags.json`

### 3) Run a single simulator timer

Create **one Gateway Timer Script** (e.g. **1000 ms**) and paste:

- `timer_script_kredsloeb_aarhus_site01_orchestrator.py`

Enable/disable the whole simulation with:

- `[kredsloeb_process]Kredsloeb/Denmark/Midtjylland/Aarhus/Site01/Config/SimEnabled`

