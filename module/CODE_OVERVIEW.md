## Module code overview (Ignition Zerobus Connector)

This document explains the runtime architecture and key classes under `module/src/main/java/com/example/ignition/zerobus`.

### High-level lifecycle

The module is a **Gateway scope** module. Ignition calls into our gateway hook, which wires up:

- configuration persistence (PersistentRecord)
- HTTP endpoints under `/system/zerobus/*`
- tag ingestion service (`TagSubscriptionService`)
- Zerobus sink/client (`ZerobusClientManager`)

There are **two gateway hooks** for Ignition API differences:

- **Ignition 8.1.x**: `ZerobusGatewayHook`
- **Ignition 8.3.x**: `ZerobusGatewayHook83`

Both implement `ZerobusRuntime`, which is the interface used by the servlet handler to call into the running module.

### Key concepts and “data path”

Two ways for events to enter:

- **Direct tag subscriptions** (recommended): subscribe to tags via `GatewayTagManager` and receive `TagChangeEvent`s in-process.
- **HTTP ingest**: POST JSON payloads to `/system/zerobus/ingest` or `/system/zerobus/ingest/batch` (e.g., Event Streams or custom scripts).

One way for events to leave:

- **Zerobus ingest** (gRPC/protobuf) via the Databricks Zerobus SDK.

The runtime data path is intentionally structured as a small pipeline:

1. **Adapter**: tag change or HTTP payload becomes a `TagEvent`
2. **Mapper**: `TagEvent → OTEvent` (`pipeline/OtEventMapper`)
3. **Buffer**: in-memory queue or disk-backed store-and-forward (`pipeline/StoreAndForwardBuffer`)
4. **Sink**: sends batches to Zerobus (`pipeline/ZerobusEventSink` → `ZerobusClientManager`)

Pipeline wiring is centralized in `pipeline/ZerobusPipelineFactory`.

### Configuration + validation

`ConfigModel` is the in-memory config model surfaced by the UI and persisted via Ignition PersistentRecords.

It contains:

- Databricks connectivity: `workspaceUrl`, `zerobusEndpoint`, OAuth client id/secret
- Target UC table: `targetTable`
- Tag selection settings:
  - `enableDirectSubscriptions` (direct subscriptions vs HTTP ingest only)
  - `tagSelectionMode`: `explicit` / `folder` / `pattern`
  - `explicitTagPaths`, `tagFolderPath`, `tagPathPattern`, `includeSubfolders`
- batching + throttling: `batchSize`, `batchFlushIntervalMs`, `maxQueueSize`, `maxEventsPerSecond`
- store-and-forward: `enableStoreAndForward`, `spoolDirectory`, watermarks, etc.
- control flags: `enabled`, `debugLogging`

Validation is done via `ConfigModel.validate()` and is enforced on save (the config servlet returns 400 + details).

### Gateway hooks

#### `ZerobusGatewayHook` (Ignition 8.1)

Responsibilities:

- register PersistentRecord: `ZerobusSettings`
- register servlet endpoints under `/system/zerobus/*`
- register Wicket-based config UI nav entry (8.1-era APIs)
- on `startup()`:
  - load persisted config
  - wire pipeline (`ZerobusPipelineFactory.create(...)`)
  - start services if `enabled` is true

#### `ZerobusGatewayHook83` (Ignition 8.3)

Responsibilities:

- register PersistentRecord: `ZerobusSettings83`
- register servlet endpoints under `/system/zerobus/*`
- register new 8.3 navigation entry (Platform → System → Zerobus Config) via `NavigationModel` + `SystemJsModule`
- on `startup()`:
  - start services if `enabled` is true

### Tag ingestion: `TagSubscriptionService`

This is the main ingestion service. It is “event-driven” and runs a periodic flush loop:

- **Start**:
  - schedules a periodic `flushBatch()` every `batchFlushIntervalMs`
  - starts direct subscriptions asynchronously (important: don’t block gateway startup by browsing large trees)
- **Direct subscriptions**:
  - uses `GatewayTagManager.subscribeAsync(...)` with a `TagChangeListener`
  - supports resolving tag targets by mode:
    - `explicit`: parse strings into `TagPath`
    - `folder`: browse under a folder root and select leaf `AtomicTag`s
    - `pattern`: browse leaf tags and filter by Java regex matched against full tag path string
- **HTTP ingest**:
  - `ZerobusServletHandler` calls `ZerobusRuntime.ingestTagEvent(...)` which delegates into `TagSubscriptionService`
- **Filtering**:
  - optional `onlyOnChange` + `numericDeadband` filtering
- **Backpressure**:
  - in disk SAF mode, it monitors spool backlog and can auto-pause/resume subscriptions
- **Sink-down behavior**:
  - flush loop checks `sink.isReady()` before draining (especially important for disk-backed SAF)

### Buffering: `pipeline/StoreAndForwardBuffer` + `saf/DiskSpool`

Two operating modes:

- **In-memory** (default): bounded queue (`maxQueueSize`), commit removes records only after successful send.
- **Disk store-and-forward** (optional): `DiskSpool` stores serialized protobuf bytes on disk, commit advances offset.

Backpressure is applied using high/low watermark percentages against `spoolMaxBytes`.

### Zerobus sink: `ZerobusClientManager` + `pipeline/ZerobusEventSink`

`ZerobusClientManager` owns the Databricks Zerobus SDK objects:

- initializes SDK + stream based on OAuth config + target table
- sends batches of `OTEvent` via the SDK
- implements error classification + backoff to avoid hot loops
- exposes diagnostics (connected/initialized status, last error, counters, etc.)

`pipeline/ZerobusEventSink` is a thin adapter that exposes:

- `isReady()` / `tryEnsureReady()`
- `send(List<OTEvent>)`

### Web layer: `/system/zerobus/*`

Endpoints are served via a servlet, not JAX-RS, for cross-version compatibility.

- `web/ZerobusConfigServlet` selects which servlet implementation to load at runtime:
  - 8.1/8.2: `web/servlet81/ZerobusConfigServletJavax`
  - 8.3+: `web/servlet83/ZerobusConfigServletJakarta`
- Both delegate to `web/ZerobusServletHandler` which implements routing:
  - `GET /health`
  - `GET /config` (redacts secret)
  - `POST /config` (save + validate; preserves secret if UI sends blank/“****”)
  - `POST /test-connection`
  - `POST /restart-services`
  - `GET /diagnostics`
  - `POST /ingest` and `POST /ingest/batch`
  - `GET /configure` serves `/web/zerobus-config.html`

The handler uses `ZerobusConfigResourceHolder` to obtain the active `ZerobusRuntime` instance.

### Where to start when changing behavior

- **Config fields/UI behavior**: `ConfigModel`, `web/ZerobusServletHandler`, and the HTML under `module/src/main/resources/web/zerobus-config.html`
- **Direct subscriptions logic**: `TagSubscriptionService` (resolve/browse/subscribe + filtering)
- **Event schema**: `module/src/main/proto/ot_event.proto` and mapper `pipeline/OtEventMapper`
- **Delivery guarantees/backpressure**: `pipeline/StoreAndForwardBuffer` and `saf/DiskSpool`
- **Zerobus integration**: `ZerobusClientManager`



