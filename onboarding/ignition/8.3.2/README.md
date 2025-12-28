# Ignition 8.3.2 Onboarding

## Configure in the Gateway UI (recommended)

1) Install/upgrade the **8.3** module:

- Gateway UI: `http://localhost:8088/app` → Configure → Modules → Install/Upgrade
- Upload: `releases/zerobus-connector-1.0.0-ignition-8.3.modl`

2) Configure in the Gateway UI:

- Open the module UI:
  - Nav: **Platform → System → Zerobus Config**
  - Direct URL: `http://localhost:8088/system/zerobus/configure`
- Set:
  - **Enable Direct Subscriptions** = ON
  - **Tag Selection Mode** = `explicit`
  - **Explicit Tag Paths** = your tag list
  - Databricks settings (Workspace URL, Zerobus Endpoint, OAuth Client ID/Secret, Target Table)
  - **Enabled** = true
- Save

3) Verify:

```bash
curl -sS http://localhost:8088/system/zerobus/diagnostics | head -n 120
```

## Optional: Event Streams mode

If you need Designer-level transforms/filters per project, you can use Event Streams
to POST to the module’s ingest endpoint.

### 1) Configure the module (Event Streams config)

Configure in UI as above, but set:
- **Enable Direct Subscriptions** = OFF

This makes the module ingest-only (it will not subscribe to tags).

### 2) Configure Event Streams to send to the module

- `POST http://<gateway-host>:<port>/system/zerobus/ingest/batch`

Keep **direct subscription disabled** if you use Event Streams (otherwise you can double-ingest).


