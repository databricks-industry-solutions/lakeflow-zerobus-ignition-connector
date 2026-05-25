# Ignition OT Ingestion Connector

Production-focused Ignition module for OT ingestion into Databricks with two exclusive sink modes:

- `zerobus`: Zerobus ingest -> Delta table
- `lakebase`: PostgreSQL sink -> Lakebase table

## Concepts (Ignition Gateway + Databricks)

### What is an Ignition Gateway?

An Ignition Gateway is the runtime server for the Ignition platform. It connects to industrial data sources (OPC UA, MQTT, PLC drivers, and others), exposes values as tags, and runs gateway-side services such as history, alarming, scripting, and eventing.

This connector runs inside the Gateway as an Ignition module (`.modl`).

### Why this connector?

The connector provides a source-agnostic ingestion path from Ignition tag events into Databricks destinations:

- Delta via Zerobus (`sinkMode=zerobus`)
- Lakebase via PostgreSQL writes (`sinkMode=lakebase`)

It supports direct tag subscriptions and HTTP ingest endpoints while keeping a consistent event model and buffered delivery path.

## Source-agnostic by design

This connector subscribes to Ignition tags, not to a specific OT protocol. Whether data originates from OPC UA, MQTT, PLC drivers, historians, or simulated tags, the runtime path is the same:

1. Tag event input
2. `TagEvent` normalization
3. `OTEvent` mapping
4. store-and-forward buffer + batch flush
5. delivery to the configured sink

Because the event payload is defined around tag observations, schema changes are not required when switching source protocols.

## Module-first scope

Primary ingestion assets:

- `module/` - Ignition module source/build
- `releases/` - prebuilt `.modl` artifacts
- `DEPLOYMENT.md` - install/configure/verify runbook
- `docker/ignition-gateway/` - optional local Gateway runtime

This module can ingest OT events directly as a standalone Ignition connector.

## Architecture

![Ignition OT ingestion options: Zerobus and Lakebase](docs/diagrams/ingestion-options-dual-sink.png)
Source: `docs/diagrams/ingestion-options-dual-sink.mmd`

## Install

Use the Release 2 artifacts for your Ignition version:

- Ignition 8.1.x release: <a href="https://github.com/databricks-industry-solutions/lakeflow-zerobus-ignition-connector/releases/tag/v2.0.0-ignition-8.1">v2.0.0-ignition-8.1</a>
- Ignition 8.3.x release: <a href="https://github.com/databricks-industry-solutions/lakeflow-zerobus-ignition-connector/releases/tag/v2.0.0-ignition-8.3">v2.0.0-ignition-8.3</a>

Asset filenames:

- Ignition 8.1.x -> `releases/zerobus-connector-1.0.10.modl`
- Ignition 8.3.x -> `releases/zerobus-connector-1.1.0-ignition-8.3.modl`

Release 2 includes:

- dual sink modes (`sinkMode=zerobus` and `sinkMode=lakebase`)
- Lakebase/PostgreSQL sink integration with connection pooling and diagnostics
- SDT compression fields in the OT event schema and sink payloads
- Databricks SDK partner/product User-Agent attribution registration

Install from Gateway UI:

- Configure -> Modules -> Install/Upgrade

## Build your own module (Gradle)

Build from source in `module/` using Gradle:

```bash
cd module

# Ignition 8.1.x artifact
./gradlew buildModule81

# Ignition 8.3.x artifact
./gradlew buildModule83
```

Generated artifacts are copied to:

- `module/releases/zerobus-connector-1.0.10.modl`
- `module/releases/zerobus-connector-1.0.10-ignition-8.3.modl`

For full installation and verification after build, see:

- <a href="./DEPLOYMENT.md">DEPLOYMENT.md</a>

## Deploy with Docker (Gateway runtime)

For local/containerized Ignition Gateway deployment, use the Docker guide:

- <a href="./docker/ignition-gateway/README.md">docker/ignition-gateway/README.md</a>

Quick start example:

```bash
cd docker/ignition-gateway
docker compose -f docker-compose.83.restore.yml up -d
```

That guide covers:

- Colima/Docker prerequisites
- normal start vs `.gwbk` restore flows
- persistent Gateway data volumes
- port mappings and runtime flags

## Configure

Configuration endpoints:

- Gateway UI: `/system/zerobus/configure`
- REST API: `/system/zerobus/config`

Key settings:

- Databricks workspace and auth
- sink selection (`zerobus` or `lakebase`)
- direct subscriptions toggle
- batching, buffering, retries, and numeric compression

For end-to-end setup and validation commands, use `DEPLOYMENT.md`.

## Ingestion modes

- **Direct subscriptions**: module subscribes to Ignition tags and ingests changes.
- **HTTP ingest-only**: disable direct subscriptions and POST events to:
  - `POST /system/zerobus/ingest`
  - `POST /system/zerobus/ingest/batch`

## Sink modes

- **`sinkMode=zerobus`**
  - `enableZerobusSink=true`
  - `enablePostgresSink=false`
  - destination: Delta via Zerobus ingest

- **`sinkMode=lakebase`**
  - `enableZerobusSink=false`
  - `enablePostgresSink=true`
  - destination: Lakebase via SQL batch inserts

Both sink modes share the same upstream ingestion and buffering flow.

## Target table schemas (required)

Create the destination table before enabling the sink:

- Zerobus target table (Delta): `examples/sql/zerobus_target_table.sql`
- Lakebase target table (PostgreSQL): `examples/sql/lakebase_raw_tags_table.sql`

Schema alignment notes for Zerobus/protobuf are documented in:

- `module/SCHEMA_ALIGNMENT.md`

## Historical note

The historical "Zerobus connector" name reflects the original single-destination path. Current connector behavior supports dual destinations (`zerobus` + `lakebase`) while preserving the same module-first ingestion architecture.

## Evolution timeline

- **Initial connector releases**: Zerobus-only ingestion path from Ignition tags to Delta.
- **Stability phase**: store-and-forward, buffering, retry, and diagnostics hardened for gateway runtime reliability.
- **Current phase**: dual-sink architecture with explicit `sinkMode` selection:
  - `zerobus` for Delta landing
  - `lakebase` for PostgreSQL/Lakebase writes

## Migration notes (legacy to `sinkMode`)

If you are upgrading from an older configuration that only used Zerobus fields:

- Set `sinkMode=zerobus`.
- Keep `enableZerobusSink=true` and `enablePostgresSink=false`.
- Existing Zerobus workspace/auth/endpoint/table settings continue to apply.

If you are enabling Lakebase:

- Set `sinkMode=lakebase`.
- Set `enableZerobusSink=false` and `enablePostgresSink=true`.
- Provide PostgreSQL fields (`postgresHost`, `postgresPort`, `postgresDatabase`, `postgresUser`, `postgresPassword`, `postgresTable`).

Recommended upgrade flow:

1. Export or GET current config (`/system/zerobus/config`).
2. Apply sink-mode fields for the target destination.
3. Run `POST /system/zerobus/test-connection`.
4. Verify with `/system/zerobus/diagnostics` before production traffic.

## Reference

### API endpoints

All endpoints are under `/system/zerobus`:

- `GET /health`
- `GET /diagnostics`
- `POST /config`
- `POST /test-connection`
- `POST /ingest`
- `POST /ingest/batch`

### Key classes

- `module/src/main/java/com/example/ignition/zerobus/ZerobusGatewayHook.java`
- `module/src/main/java/com/example/ignition/zerobus/ZerobusGatewayHook83.java`
- `module/src/main/java/com/example/ignition/zerobus/TagSubscriptionService.java`
- `module/src/main/java/com/example/ignition/zerobus/ZerobusClientManager.java`
- `module/src/main/java/com/example/ignition/zerobus/PostgresClientManager.java`
- `module/src/main/java/com/example/ignition/zerobus/pipeline/ZerobusPipelineFactory.java`
- `module/src/main/proto/ot_event.proto`
