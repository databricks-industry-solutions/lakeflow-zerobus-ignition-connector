### Renewables windfarm simulation (Ignition) — example

This folder contains an end-to-end example to simulate a small windfarm in Ignition using **Memory tags** and a **Gateway Timer Script**, then ingest it with the Zerobus connector.

### What’s included

- **`renewables_sim_windfarm01_tags.json`**: Ignition Tag Browser JSON export you can import into a tag provider.
- **`timer_script_windfarm01.py`**: Jython Gateway Timer script that updates the tags with a realistic wind→power curve.

### Prerequisites

- Ignition Gateway running (8.1 or 8.3).
- Zerobus module installed (optional, only needed if you want ingestion to Databricks).

### 1) Create the tag provider

In the Gateway UI:

- Go to **Configure → Tags → Realtime Tag Providers**
- Create a **Standard Tag Provider** (internal provider) named **`renewables`**
- Ensure it is:
  - **Enabled**
  - **NOT Read Only**

> The provider name **must** match `renewables` exactly, because all tag paths in this example start with `[renewables]...`.

### 2) Import the tags

In the Designer connected to the same gateway:

- Open the **Tag Browser**
- Select provider **`renewables`**
- Right-click → **Import**
- Choose **JSON**
- Import `examples/renewables_sim/renewables_sim_windfarm01_tags.json`

You should now see tags under:

- `[renewables]Renewables/Windfarm01/Site/...`
- `[renewables]Renewables/Windfarm01/Turbines/T01/...` (and T02/T03)

### 3) Add the Gateway Timer Script (simulator)

In the Designer:

- Go to **Scripting → Gateway Events → Timer**
- Create a timer event (or edit an existing one)
- Set:
  - **Delay Type**: Fixed Delay
  - **Delay (ms)**: 1000
  - **Enabled**: true
- Paste the contents of `examples/renewables_sim/timer_script_windfarm01.py` into the Timer script editor.

### 4) Validate it’s working (Ignition)

- Watch these tags; they should change about once per second:
  - `[renewables]Renewables/Windfarm01/Site/WindSpeed_mps`
  - `[renewables]Renewables/Windfarm01/Turbines/T01/Electrical/Power_kW`

If values stay constant, check the Gateway logs for messages from logger name **`renewables`**.

### Configure it (Renewables AU assumptions, but tunable)

This example includes editable config tags under:

- `[renewables]Renewables/Windfarm01/Config/*`

Key knobs:

- **`SimEnabled`**: set false to pause simulation
- **`UpdateEveryMs`**: throttle updates (e.g., 1000, 2000, 5000)
- **`MeanWind_mps`**, **`TurbulenceSigma`**, **`WindDirNoiseSigma_deg`**: site wind regime (typical AU wind sites: mean ~8–10 m/s)
- **`CutIn_mps`**, **`RatedWind_mps`**, **`CutOut_mps`**: turbine power curve
- **`RatedPower_T01_kW`** / `T02` / `T03`: nameplate ratings
- **`FaultRatePerSecond`**, **`FaultMinSeconds`**, **`FaultMaxSeconds`**: fault frequency/duration
- **`YawGain`**, **`YawNoiseSigma_deg`**, **`YawDerateExponent`**: yaw response + derating

The timer script reads these values (cached, refreshed every ~5s) so you can tune behavior live without editing code.

### 5) Ingest to Databricks with Zerobus (optional)

For Ignition 8.1/8.3, the recommended ingest path is **direct subscriptions** (no Event Stream scripts required).

Tag selection modes supported for direct subscriptions:

- **Explicit**: subscribe to exactly the tag paths you list
- **Folder**: subscribe to all Atomic Tags under one folder root (optionally include subfolders)
- **Pattern**: Java regex over full tag path (useful to subscribe multiple providers / a whole site)

Add a few example paths in the Zerobus config UI:

- `[renewables]Renewables/Windfarm01/Site/WindSpeed_mps`
- `[renewables]Renewables/Windfarm01/Site/Power_Total_kW`
- `[renewables]Renewables/Windfarm01/Turbines/T01/Electrical/Power_kW`
- `[renewables]Renewables/Windfarm01/Turbines/T02/Electrical/Power_kW`
- `[renewables]Renewables/Windfarm01/Turbines/T03/Electrical/Power_kW`

Then verify:

- `GET /system/zerobus/diagnostics` shows `Direct Subscriptions: <N> tags`
- Your target table receives rows with `tag_provider = 'renewables'`

### Databricks SQL: last 2 minutes by provider

```sql
SELECT
  source_system,
  tag_provider,
  COUNT(*) AS events_2m,
  MAX(from_unixtime(unix_timestamp(ingestion_timestamp))) AS last_ingested_at
FROM ignition_demo.scada_data.tag_events
WHERE unix_timestamp(ingestion_timestamp) >= unix_timestamp() - 120
GROUP BY source_system, tag_provider
ORDER BY events_2m DESC, last_ingested_at DESC;
```


