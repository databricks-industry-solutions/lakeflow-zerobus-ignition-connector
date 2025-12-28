## Zerobus Connector — Production Deployment & Developer Build

This doc is the production runbook for deploying the **Ignition Zerobus Connector** module, plus a short **developer build** section for generating the `.modl` artifacts.

## Production deployment

### Choose the correct module artifact

- **Ignition 8.1.x**: use `releases/zerobus-connector-1.0.0.modl`
- **Ignition 8.3.x**: use `releases/zerobus-connector-1.0.0-ignition-8.3.modl`

### Install / upgrade

- Gateway UI → Configure → Modules → Install/Upgrade → upload the `.modl`

### Configure (GUI-only)

The module is configured in the Gateway UI and persisted in the Gateway internal DB. Your `.modl` does **not** contain your credentials.

Open the configuration page:
- **Ignition 8.1.x**: `http://<gateway-host>:<port>/system/zerobus/configure`
- **Ignition 8.3.x**:
  - Nav: **Platform → System → Zerobus Config**
  - Direct: `http://<gateway-host>:<port>/system/zerobus/configure`

#### Recommended mode: Direct subscriptions

- **Enable Direct Subscriptions**: ON
- **Tag Selection Mode**: `explicit`
- **Explicit Tag Paths**: add the tag paths you want to ingest
- **Databricks**:
  - Workspace URL
  - Zerobus Endpoint
  - OAuth Client ID
  - OAuth Client Secret
  - Target Table (format: `catalog.schema.table`)
- **Enabled**: ON

Save. The module should stay running even if configuration is incomplete; it will surface validation errors in diagnostics and keep services stopped until fixed.

#### Ingest-only mode (Event Streams / external producer)

If you want the module to only accept HTTP ingest:
- **Enable Direct Subscriptions**: OFF

In this mode, tag selection fields do not apply.

### Verify (Gateway)

Diagnostics endpoint:
- `GET http://<gateway-host>:<port>/system/zerobus/diagnostics`

What to look for:
- `Module Enabled: true`
- `Initialized: true`
- `Connected: true` (or a clear last error)
- `Total Events Received` / `Total Events Sent` increasing
- `Direct Subscriptions: <N> tags` (only if direct subscriptions is ON)

### Verify (Databricks)

If your table has `ingestion_timestamp` as `TIMESTAMP`:

```sql
SELECT
  source_system_id,
  COUNT(*) AS rows_last_10m
FROM ignition_demo.scada_data.tag_events
WHERE ingestion_timestamp >= current_timestamp() - INTERVAL 10 MINUTES
GROUP BY source_system_id
ORDER BY rows_last_10m DESC;
```

## Troubleshooting

### Module installed but no events

- Confirm **Enabled** is ON and config saved successfully.
- If using direct subscriptions:
  - confirm tag paths exist and are changing
  - confirm `Direct Subscriptions: <N> tags` is non-zero in diagnostics
- Temporarily enable `debugLogging` in the module config and review Gateway logs.

### Ignition 8.3 module won’t install

You likely uploaded the 8.1 artifact. Use `releases/zerobus-connector-1.0.0-ignition-8.3.modl`.

## Developer build (produce `.modl`)

### Requirements

- **JDK 17**
- Ignition installs available locally for SDK jars:
  - 8.1: `/usr/local/ignition8.1`
  - 8.3: `/usr/local/ignition`

### Build

```bash
cd module
JAVA_HOME=/opt/homebrew/opt/openjdk@17 PATH=/opt/homebrew/opt/openjdk@17/bin:$PATH \
  ./gradlew buildModule81
```

```bash
cd module
JAVA_HOME=/opt/homebrew/opt/openjdk@17 PATH=/opt/homebrew/opt/openjdk@17/bin:$PATH \
  ./gradlew buildModule83
```

Outputs:
- 8.1: `module/build-user-8.1/modules/zerobus-connector-1.0.0.modl`
- 8.3: `module/build-user-8.3/modules/zerobus-connector-1.0.0-ignition-8.3.modl`


