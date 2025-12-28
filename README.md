## Ignition Zerobus Connector

**Version**: `1.0.0`  
**Purpose**: Stream Ignition tag-change events to Databricks Delta tables via Zerobus (gRPC + protobuf).  
**Ignition compatibility**: **8.1.x** and **8.3.x** (different `.modl` artifacts).  
**Configuration**: via the **Ignition Gateway UI**.

## Table of contents

- [Prerequisites](#prerequisites)
- [Production deployment](#production-deployment)
- [Release artifacts (two `.modl` files)](#release-artifacts-two-modl-files)
- [Configuration (GUI)](#configuration-gui)
- [Verify ingestion](#verify-ingestion)
- [Monitoring & troubleshooting](#monitoring--troubleshooting)
- [Developer build](#developer-build)
- [Reference](#reference)

## Prerequisites

### Ignition / Gateway

- **Gateway admin access** to install modules and edit module configuration.
- **Outbound network access** from the Gateway host to Databricks:
  - HTTPS to your workspace URL (`https://<workspace-host>`)
  - Connectivity to the Zerobus endpoint you configure

### Databricks OAuth (service principal)

You need an OAuth **client ID/secret** for a Databricks **service principal** that is allowed to write to your target Unity Catalog table.

Minimum recommended Unity Catalog permissions for the service principal:

```sql
-- replace these with your values
GRANT USE CATALOG ON CATALOG <catalog> TO `<service_principal_name_or_id>`;
GRANT USE SCHEMA ON SCHEMA <catalog>.<schema> TO `<service_principal_name_or_id>`;
GRANT MODIFY ON TABLE <catalog>.<schema>.<table> TO `<service_principal_name_or_id>`;
```

Notes:
- `MODIFY` covers writes to an existing table (INSERT/UPDATE/DELETE as applicable).
- If you want the pipeline to create tables automatically (not typical for production), grant `CREATE` on the schema instead.

## Production deployment

For the full production runbook (install, configure, verify, troubleshooting), see `DEPLOYMENT.md`.

At a glance:
- Install the correct `.modl` for your Ignition version (below).
- Configure in the Gateway UI at `/system/zerobus/configure`.
- Verify via `/system/zerobus/diagnostics` and Databricks SQL.

## Release artifacts (two `.modl` files)

There are **two** prebuilt module packages under `releases/`:

- **`releases/zerobus-connector-1.0.0.modl`**:
  - **Install on**: Ignition **8.1.x** (and 8.2.x if you run it)
  - **Why**: the packaged `module.xml` sets `<requiredIgnitionVersion>` to `8.1.0`

- **`releases/zerobus-connector-1.0.0-ignition-8.3.modl`**:
  - **Install on**: Ignition **8.3.x**
  - **Why**: the packaged `module.xml` sets `<requiredIgnitionVersion>` to `8.3.0`

### What’s different between them?

Ignition enforces compatibility based on `module.xml` during install. Because 8.3 refuses modules whose `requiredIgnitionVersion` is below 8.3, we ship two `.modl` artifacts.

The **runtime behavior and code are the same**; the important differences are:

- **`module.xml` gate**: different `<requiredIgnitionVersion>` value, produced by the Gradle `-PminIgnitionVersion=...` build flag.
- **Servlet API at runtime**:
  - Ignition 8.1 uses **`javax.servlet`**
  - Ignition 8.3 uses **`jakarta.servlet`**
  - The module includes both servlet implementations and selects the right one at runtime via `module/src/main/java/com/example/ignition/zerobus/web/ZerobusConfigServlet.java`.

## Quick start

### 1) Databricks: create the Bronze table

- Create the target Delta table in Databricks (Bronze).
- The Bronze schema matches `module/src/main/proto/ot_event.proto`.

### 2) Install the module (.modl)

- **Ignition 8.1.x**: install `releases/zerobus-connector-1.0.0.modl`
- **Ignition 8.3.x**: install `releases/zerobus-connector-1.0.0-ignition-8.3.modl`

Gateway UI → Config → Modules → Install/Upgrade → upload the `.modl`.

### 3) Configure (UI-first; no Designer required)

### Ignition 8.1.x (GUI configuration)

1) Install `releases/zerobus-connector-1.0.0.modl` (Gateway UI → Config → Modules).
2) Configure in UI: `http://localhost:8099/system/zerobus/configure`
3) For the standard “subscribe to tags” mode:
   - **Enable Direct Subscriptions** = ON
   - **Tag Selection Mode** = `explicit`
   - **Explicit Tag Paths** = your tag list
4) Set Databricks fields + **Enabled** = ON, then **Save**.

### Ignition 8.3.x (GUI configuration)

1) Install `releases/zerobus-connector-1.0.0-ignition-8.3.modl` (Gateway UI → `http://localhost:8088/app` → Configure → Modules).
2) Configure in UI:
   - Nav: **Platform → System → Zerobus Config**
   - Direct: `http://localhost:8088/system/zerobus/configure`
3) For the standard “subscribe to tags” mode:
   - **Enable Direct Subscriptions** = ON
   - **Tag Selection Mode** = `explicit`
   - **Explicit Tag Paths** = your tag list
4) Set Databricks fields + **Enabled** = ON, then **Save**.

### 4) Verify

```bash
curl -sS http://localhost:8099/system/zerobus/diagnostics | egrep 'Module Enabled|Initialized|Connected|Total Events Received|Total Events Sent|Direct Subscriptions|Last Flush'
```

## Configuration (GUI)

Key fields:
- **Databricks**: `workspaceUrl`, `zerobusEndpoint`, `oauthClientId`, `oauthClientSecret`, `targetTable`
- **Source identity**: `sourceSystemId` (gateway/site identifier; shows up in Bronze)
- **Direct subscriptions toggle**: `enableDirectSubscriptions`
- **Tag selection**:
  - `tagSelectionMode: "explicit"`
  - `explicitTagPaths: ["[provider]Folder/Tag", ...]`
- **Batching**: `batchSize`, `batchFlushIntervalMs`, `maxQueueSize`, `maxEventsPerSecond`

If you are using Event Streams or an external producer to POST events, you can run the module in **ingest-only** mode:
- Set **Enable Direct Subscriptions** = OFF

Important: don’t double-ingest—use either direct subscriptions or ingest-only producers for a given tag set.

## Verify ingestion

### 1) Gateway-side verification (diagnostics)

- 8.1: `GET http://<gateway-host>:<port>/system/zerobus/diagnostics`
- 8.3: `GET http://<gateway-host>:<port>/system/zerobus/diagnostics`

Look for:
- `Module Enabled: true`
- `Connected: true` (or at least `Initialized: true`)
- `Total Events Received` and `Total Events Sent` increasing

### 2) Databricks verification (SQL)

If your table has a `TIMESTAMP` column named `ingestion_timestamp`:

```sql
SELECT
  source_system_id,
  COUNT(*) AS rows_last_10m
FROM ignition_demo.scada_data.tag_events
WHERE ingestion_timestamp >= current_timestamp() - INTERVAL 10 MINUTES
GROUP BY source_system_id
ORDER BY rows_last_10m DESC;
```

## API endpoints

All endpoints are under `/system/zerobus`:
- `GET /health`
- `GET /diagnostics`
- `POST /config`
- `POST /test-connection`
- `POST /ingest` (single JSON event)
- `POST /ingest/batch` (JSON array of events)

## Monitoring & troubleshooting

### First place to look

`GET /system/zerobus/diagnostics` shows:
- Zerobus connected/initialized state
- total events received/sent
- queue size and flush cadence
- subscription count

### Common issues

- **Module won’t install on 8.3**: you likely uploaded the 8.1 artifact. Use `releases/zerobus-connector-1.0.0-ignition-8.3.modl`.
- **Events not increasing**:
  - verify the tag paths exist and are changing
  - check `Direct Subscriptions: N tags` is non-zero
  - set `debugLogging: true` temporarily (then reconfigure)
- **Sample_Tags show `Error_Configuration` or OPC UA flaps**:
  - if running both gateways locally, avoid OPC UA port collisions and mismatched endpoints
  - example fix: point the 8.3 OPC UA connection at `opc.tcp://localhost:62542` (8.3’s OPC UA server)
- **`Target table must be in format catalog.schema.table`**:
  - ensure there are exactly 3 dot-separated parts and the table name does not contain extra dots

## Developer build

### 1) Prerequisites (local dev machine)

- **JDK 17** installed (Gradle/tooling).
- **Ignition SDK jars available locally** (used as `compileOnly` dependencies):
  - **8.1.x** install at: `/usr/local/ignition8.1`
  - **8.3.x** install at: `/usr/local/ignition`

### 2) Code flow explainer (runtime)

#### 2.1) High-level architecture

Two ways for events to enter the module:
- **Direct subscriptions** (recommended): in-JVM tag change callbacks from Ignition’s TagManager
- **HTTP ingest** (ingest-only mode): external producer POSTs JSON to module endpoints

One way for events to leave the module:
- **Zerobus ingest over gRPC/protobuf** to the Databricks Zerobus endpoint

#### 2.2) Lifecycle and configuration

**Startup**
- Gateway hook entrypoints:
  - Ignition **8.1.x**: `com.example.ignition.zerobus.ZerobusGatewayHook`
  - Ignition **8.3.x**: `com.example.ignition.zerobus.ZerobusGatewayHook83`
- PersistentRecord schema is registered (tables created if missing).
- Configuration is loaded from the Gateway internal DB into `com.example.ignition.zerobus.ConfigModel`.
- Services start **only if** configuration is valid enough to run (and module is enabled). Invalid config **does not fault the module**; it keeps services stopped and exposes the error in diagnostics.

**Save/apply configuration**
- New values are persisted to PersistentRecord.
- Runtime `ConfigModel` is updated (`updateFrom(...)`).
- Services are restarted only if necessary (and without crashing the module on validation errors).
- OAuth client secret is stored in the Gateway internal DB (masked in UI); leaving it blank preserves the existing value.

#### 2.3) Data path: Direct subscriptions mode

1) **Tag change happens**: Ignition calls into the module via TagManager subscription callbacks.  
2) **Module enqueues events**: `TagSubscriptionService` converts the change to internal `TagEvent` objects and pushes them onto a bounded queue.  
3) **Batch/flush loop**: flushes based on `batchSize` and `batchFlushIntervalMs` (plus rate limits/backpressure).  
4) **Send to Databricks via Zerobus**: `ZerobusClientManager` converts events to protobuf (`module/src/main/proto/ot_event.proto`) and streams them over gRPC to Databricks Zerobus (with reconnect/recovery on transient failures).

#### 2.4) Data path: HTTP ingest mode (ingest-only)

Prerequisite: set **Enable Direct Subscriptions** = OFF in the module UI.

1) **Producer POSTs JSON**:
   - `POST /system/zerobus/ingest` (single)
   - `POST /system/zerobus/ingest/batch` (batch)
2) **Servlet routes the request**:
   - `.../web/ZerobusConfigServlet` (dispatcher)
   - `.../web/ZerobusServletHandler` (shared request parsing/routing)
3) **Events are enqueued**: same queue as direct subscriptions.
4) **Batch/flush/send**: same flush loop and Zerobus sender as direct subscriptions.

### 3) Build artifacts

#### 3.1) Build the Ignition 8.1.x module (`.modl`)

```bash
cd module
JAVA_HOME=/opt/homebrew/opt/openjdk@17 PATH=/opt/homebrew/opt/openjdk@17/bin:$PATH \
  ./gradlew buildModule81
```

Output: `module/build-user-8.1/modules/zerobus-connector-1.0.0.modl`

#### 3.2) Build the Ignition 8.3.x module (`.modl`)

```bash
cd module
JAVA_HOME=/opt/homebrew/opt/openjdk@17 PATH=/opt/homebrew/opt/openjdk@17/bin:$PATH \
  ./gradlew buildModule83
```

Output: `module/build-user-8.3/modules/zerobus-connector-1.0.0-ignition-8.3.modl`

#### 3.3) Where release artifacts go

After building, the Gradle task also copies the `.modl` into the repo-level `releases/` directory.

## Reference

### Key classes

- **`module/src/main/java/com/example/ignition/zerobus/ZerobusGatewayHook.java`**: module lifecycle; loads/saves config; starts/stops services; registers HTTP endpoints under `/system/zerobus/*`.
- **`module/src/main/java/com/example/ignition/zerobus/TagSubscriptionService.java`**: tag event processing:
  - direct mode subscriptions via TagManager
  - HTTP ingest queueing via `/ingest` and `/ingest/batch`
  - batching + rate limiting + flush loop
- **`module/src/main/java/com/example/ignition/zerobus/ZerobusClientManager.java`**: manages Zerobus client; converts events to protobuf and streams to Databricks.
- **Servlet compatibility layer**:
  - `.../web/ZerobusConfigServlet.java` selects `javax` vs `jakarta` servlet implementation at runtime.
  - `.../web/ZerobusServletHandler.java` holds shared request parsing and routing.
- **Schema**: `module/src/main/proto/ot_event.proto`

### End-to-end data flow

**Direct subscriptions**
1) Tag change event → `TagSubscriptionService` listener  
2) Convert to internal `TagEvent` → queue  
3) Flush loop batches → `ZerobusClientManager`  
4) Protobuf (OTEvent) → Zerobus stream → Delta

**HTTP ingest (Event Streams / external producer)**
1) Producer POSTs JSON → `/system/zerobus/ingest` or `/ingest/batch`  
2) Handler parses + enqueues `TagEvent`s  
3) Batching + streaming as above
