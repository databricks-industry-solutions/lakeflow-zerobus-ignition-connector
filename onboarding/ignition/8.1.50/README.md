# Ignition 8.1.50 Onboarding (GUI configuration)

## Configure in the Gateway UI (recommended)

1) **Install/upgrade** the **8.1** module:

- Gateway UI: `http://localhost:8099/web/home` → Config → Modules → Install/Upgrade
- Upload: `releases/zerobus-connector-1.0.0.modl`

2) **Configure in the Gateway UI (no scripts)**:

- Open the module UI (nav item: **Zerobus Configuration**), or direct:
  - `http://localhost:8099/system/zerobus/configure`
- Set:
  - **Enable Direct Subscriptions** = ON
  - **Tag Selection Mode** = `explicit`
  - **Explicit Tag Paths** = your tag list
  - Databricks settings (Workspace URL, Zerobus Endpoint, OAuth Client ID/Secret, Target Table)
  - **Enabled** = true
- Save

3) **Verify**:

```bash
curl -sS http://localhost:8099/system/zerobus/diagnostics | head -n 120
```

You should see:
- `Module Enabled: true`
- `Direct Subscriptions: <N> tags`
- `Total Events Received/Sent` increasing

## Event Streams / HTTP ingest (optional)

If you want to ingest only via HTTP endpoints, disable direct subscriptions:
- **Enable Direct Subscriptions** = OFF

Then have your producer POST to:
- `POST http://<gateway-host>:<port>/system/zerobus/ingest`
- `POST http://<gateway-host>:<port>/system/zerobus/ingest/batch`

