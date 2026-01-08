### Pluspetrol (Argentina) — Oil & Gas demo tag model (Ignition) — example

This folder contains a lightweight **Ignition Tag Browser JSON export** you can import into an **Ignition 8.1** gateway tag provider to demo the Zerobus connector with an oil & gas telemetry shape (wells → gathering → processing → tanks/flare).

### What’s included

- **`pluspetrol_la_calera_tags.json`**: Ignition Tag Browser JSON export (Memory tags).
- **`timer_script_pluspetrol_la_calera.py`**: Jython Gateway Timer script that simulates wells → separator → compressor → tanks/flare telemetry (normal ops).
- **`timer_script_pluspetrol_la_calera_upsets.py`**: Jython Gateway Timer script that injects occasional upsets/alarms (slow cadence) for a more “wow” demo.

### 1) Create the tag provider

In the Gateway UI:

- Go to **Configure → Tags → Realtime Tag Providers**
- Create a **Standard Tag Provider** named **`pluspetrol`**
- Ensure it is:
  - **Enabled**
  - **NOT Read Only**

> The provider name **must** match `pluspetrol` exactly, because all tag paths in this example start with `[pluspetrol]...`.

### 2) Import the tags

In the Designer connected to the same gateway:

- Open the **Tag Browser**
- Select provider **`pluspetrol`**
- Right-click → **Import**
- Choose **JSON**
- Import `examples/pluspetrol_la_calera/pluspetrol_la_calera_tags.json`

You should now see tags under:

- `[pluspetrol]Pluspetrol/Argentina/LaCalera/...`

### 3) Configure Zerobus connector (optional)

In Zerobus connector config, add a few explicit tag paths (examples):

- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Wells/PadA/W01/Wellhead/Pressure_bar`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Processing/Separator01/Level_pct`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Tanks/Tank01/Level_pct`

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
- Paste the contents of `examples/pluspetrol_la_calera/timer_script_pluspetrol_la_calera.py` into the Timer script editor.

Optional (recommended for demos):

- Create a **second** timer event with:
  - **Delay (ms)**: 5000 (or 10000)
  - **Enabled**: true
- Paste `examples/pluspetrol_la_calera/timer_script_pluspetrol_la_calera_upsets.py`

You should see these tags change about once per second:

- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Processing/Separator01/Level_pct`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Processing/Compressor01/DischargePressure_bar`
- `[pluspetrol]Pluspetrol/Argentina/LaCalera/Tanks/Tank01/Level_pct`


