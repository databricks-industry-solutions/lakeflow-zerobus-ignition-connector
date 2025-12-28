# Ignition 8.3.2 Onboarding

This is a short, version-specific pointer to the module UI in Ignition **8.3.2**.

For the full runbook (prereqs, configuration fields, verification SQL, troubleshooting), see `DEPLOYMENT.md`.

## 1) Install the module

- Gateway UI: `http://<gateway-host>:<port>/app` → Configure → Modules → Install/Upgrade
- Upload: `releases/zerobus-connector-1.0.0-ignition-8.3.modl`

## 2) Open the configuration UI

- Nav: **Platform → System → Zerobus Config**
- Direct URL: `http://<gateway-host>:<port>/system/zerobus/configure`

## 3) Quick verify

```bash
curl -sS http://<gateway-host>:<port>/system/zerobus/diagnostics | head -n 120
```

## Optional: Event Streams mode

If you need Designer-level transforms/filters per project, you can use Event Streams
to POST to the module’s ingest endpoint.

### 1) Configure the module (ingest-only)

In the module UI, set **Enable Direct Subscriptions** = OFF.

This makes the module ingest-only (it will not subscribe to tags).

### 2) Configure Event Streams to send to the module

- `POST http://<gateway-host>:<port>/system/zerobus/ingest/batch`

Keep **direct subscription disabled** if you use Event Streams (otherwise you can double-ingest).


