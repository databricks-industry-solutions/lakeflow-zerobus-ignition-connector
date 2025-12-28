# Ignition 8.1.50 Onboarding (GUI configuration)

This is a short, version-specific pointer to the module UI in Ignition **8.1.50**.

For the full runbook (prereqs, configuration fields, verification SQL, troubleshooting), see `DEPLOYMENT.md`.

## 1) Install the module

- Gateway UI: `http://<gateway-host>:<port>/web/home` → Config → Modules → Install/Upgrade
- Upload: `releases/zerobus-connector-1.0.0.modl`

## 2) Open the configuration UI

- Nav item: **Zerobus Configuration**
- Direct URL: `http://<gateway-host>:<port>/system/zerobus/configure`

## 3) Quick verify

```bash
curl -sS http://<gateway-host>:<port>/system/zerobus/diagnostics | head -n 120
```

If you need ingest-only mode, use the same endpoints described in `DEPLOYMENT.md` under “Ingest-only mode”.
