### Tilt windfarm simulation (Ignition) — example

This folder contains an end-to-end example to simulate a small windfarm in Ignition using **Memory tags** and a **Gateway Timer Script**, then ingest it with the Zerobus connector.

### What’s included

- **`tilt_sim_windfarm01_tags.json`**: Ignition Tag Browser JSON export you can import into a tag provider.
- **`timer_script_windfarm01.py`**: Jython Gateway Timer script that updates the tags with a realistic wind→power curve.

### Prerequisites

- Ignition Gateway running (8.1 or 8.3).
- Zerobus module installed (optional, only needed if you want ingestion to Databricks).

### 1) Create the tag provider

In the Gateway UI:

- Go to **Configure → Tags → Realtime Tag Providers**
- Create a **Standard Tag Provider** (internal provider) named **`tilt_sim`**
- Ensure it is:
  - **Enabled**
  - **NOT Read Only**

> The provider name **must** match `tilt_sim` exactly, because all tag paths in this example start with `[tilt_sim]...`.

### 2) Import the tags

In the Designer connected to the same gateway:

- Open the **Tag Browser**
- Select provider **`tilt_sim`**
- Right-click → **Import**
- Choose **JSON**
- Import `examples/tilt_sim/tilt_sim_windfarm01_tags.json`

You should now see tags under:

- `[tilt_sim]Tilt/Windfarm01/Site/...`
- `[tilt_sim]Tilt/Windfarm01/Turbines/T01/...` (and T02/T03)

### 3) Add the Gateway Timer Script (simulator)

In the Designer:

- Go to **Scripting → Gateway Events → Timer**
- Create a timer event (or edit an existing one)
- Set:
  - **Delay Type**: Fixed Delay
  - **Delay (ms)**: 1000
  - **Enabled**: true
- Paste the contents of `examples/tilt_sim/timer_script_windfarm01.py` into the Timer script editor.

### 4) Validate it’s working (Ignition)

- Watch these tags; they should change about once per second:
  - `[tilt_sim]Tilt/Windfarm01/Site/WindSpeed_mps`
  - `[tilt_sim]Tilt/Windfarm01/Turbines/T01/Electrical/Power_kW`

If values stay constant, check the Gateway logs for messages from logger name **`tilt_sim`**.

### 5) Ingest to Databricks with Zerobus (optional)

The module’s current **direct subscriptions** implementation supports **`tagSelectionMode = explicit` only**.
That means you must list the specific tag paths you want to ingest (folder/pattern selection is not applied at runtime yet).

Add a few example paths in the Zerobus config UI:

- `[tilt_sim]Tilt/Windfarm01/Site/WindSpeed_mps`
- `[tilt_sim]Tilt/Windfarm01/Site/Power_Total_kW`
- `[tilt_sim]Tilt/Windfarm01/Turbines/T01/Electrical/Power_kW`
- `[tilt_sim]Tilt/Windfarm01/Turbines/T02/Electrical/Power_kW`
- `[tilt_sim]Tilt/Windfarm01/Turbines/T03/Electrical/Power_kW`

Then verify:

- `GET /system/zerobus/diagnostics` shows `Direct Subscriptions: <N> tags`
- Your target table receives rows with `tag_provider = 'tilt_sim'`

### Databricks SQL: last 2 minutes by provider

```sql
SELECT
  source_system,
  tag_provider,
  COUNT(*) AS events_2m,
  MAX(from_unixtime(ingestion_timestamp/1000)) AS last_ingested_at
FROM ignition_demo.scada_data.tag_events
WHERE from_unixtime(ingestion_timestamp/1000) >= current_timestamp() - INTERVAL 2 MINUTES
GROUP BY source_system, tag_provider
ORDER BY events_2m DESC, last_ingested_at DESC;
```


