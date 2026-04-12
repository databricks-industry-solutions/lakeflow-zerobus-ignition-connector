# PRD.md — AGL OT Lakehouse Demo (Zerobus + Ignition Gateway)

> **This document is the single source of truth for a Claude Code Ralph Loop.**
> Iterate through all requirements (`FR-*`, `NFR-*`) until every acceptance criterion (`AC-*`) is satisfied.
> When all work is complete and verified, output `<promise>DONE</promise>`.

---

## Meta

| Field | Value |
|---|---|
| Product | AGL OT Lakehouse Demo |
| Repo branch | `agl-demo` on `pravinva/lakeflow-ignition-zerobus-connector` |
| Stack | Node.js 20+, React 18+, Tailwind CSS, Recharts/Tremor, Express, Databricks SQL Connector, Zerobus JS SDK |
| Target audience | Head of Asset Intelligence, AGL Energy |
| Demo env | Azure Databricks (`australiaeast`), Unity Catalog enabled, Zerobus Public Preview |

---

## 1 · Problem statement

AGL Energy operates 2M+ historian tags across coal, gas, hydro, wind, and battery assets. Their current stack uses traditional historians, which often introduce:

- **Vendor lock-in**: data trapped in proprietary formats; expensive licensing per-tag.
- **Operational overhead**: separate infrastructure for ingestion (interfaces / connectors), buffer nodes, and archive servers for every new site.
- **New-asset onboarding friction**: each new battery (e.g., Liddell 500 MW, Tomago 500 MW) or wind farm (Hexham 600 MW, Pottinger 831 MW) requires standing up and configuring PI collectors, buffer/relay nodes, and historian servers before a single tag flows.
- **Compression myth**: "Swinging door" compression is often cited as a unique advantage of proprietary historians. Our Zerobus connector **already implements Swinging Door Trending (SDT) compression at the edge/connector layer**, giving identical compression semantics — but writing into open Delta tables instead of a proprietary archive.

John has stated he believes a **lakehouse can standardize all asset data into open table formats** and that current approaches carry too much operational overhead. This demo proves him right.

---

## 2 · Solution overview

### Compression architecture (critical differentiator)

The system applies **two layers of compression**, directly analogous to (and exceeding) traditional historian stacks:

| Layer | Traditional equivalent | Our Implementation | Where it runs |
|---|---|---|---|
| **Exception reporting** | Interface ExDev deadband | Configurable deadband in Ignition tag provider | Ignition Gateway |
| **Swinging Door Trending** | Archive CompDev | SDT algorithm in the Zerobus connector (`agl-demo` branch) | Connector (edge/app layer) |
| **Columnar encoding** | *(none — proprietary binary)* | Delta Lake dictionary, RLE, bit-packing, Zstd | Storage layer (Delta) |

This means:
- We match common historian compression semantics at the connector level (SDT with configurable CompDev).
- We **add** columnar compression on top.
- All data lands in open Parquet/Delta — queryable by SQL, Spark, Python, any tool.

### System architecture

```
┌────────────────────┐
│  Ignition Gateway   │  (simulated wind + battery tags)
│  OPC-UA Tag Provider│
│  + Exception filter │  ← Layer 1: deadband at source
└────────┬───────────┘
         │ Tag change events (post-exception)
         ▼
┌────────────────────────────┐
│  Lakeflow Ignition          │
│  Zerobus Connector          │
│  + SDT Compression Engine   │  ← Layer 2: swinging door at connector
│  (agl-demo branch)          │
└────────┬───────────────────┘
         │ gRPC / Protobuf (compressed stream)
         ▼
┌────────────────────┐
│  Zerobus Ingest     │  Serverless — no Kafka, no broker
│  (Databricks)       │
└────────┬───────────┘
         │ Buffered write  ← Layer 3: Delta columnar compression
         ▼
┌────────────────────┐
│  Delta Tables       │  Unity Catalog governed
│  (Bronze / Silver)  │
└────────┬───────────┘
         │ SQL / REST
         ▼
┌────────────────────┐
│  Node.js Frontend   │  Live dashboards, metrics, compression view
│  (this app)         │
└────────────────────┘
```

---

## 3 · Phased implementation plan

Claude Code must implement in this order. Complete all requirements in a phase before moving to the next.

### Phase 1 — Project scaffold and data layer
`FR-001` through `FR-005`

### Phase 2 — Ignition simulator and Zerobus integration (with SDT)
`FR-006` through `FR-009`, `FR-028`

### Phase 3 — Node.js frontend: live dashboards
`FR-010` through `FR-017`

### Phase 4 — Compression view and architecture comparison
`FR-018` through `FR-022`

### Phase 5 — Polish, scenarios, and demo readiness
`FR-023` through `FR-027`

---

## 4 · Data model

### 4.1 Bronze table: `agl_demo.ot.raw_tags`

| Column | Type | Description |
|---|---|---|
| `event_timestamp` | `TIMESTAMP` | Source timestamp from Ignition |
| `ingest_timestamp` | `TIMESTAMP` | Time Zerobus persists to Delta |
| `asset_id` | `STRING` | Unique asset identifier (e.g., `wind_hexham_t01`) |
| `asset_type` | `STRING` | `wind_turbine` \| `battery_bess` \| `solar` \| `gas` |
| `tag_name` | `STRING` | Full tag path (e.g., `generator/speed_rpm`) |
| `tag_value` | `DOUBLE` | Numeric value |
| `quality` | `INT` | OPC quality code (192 = good) |
| `source_system` | `STRING` | `ignition_sim` for demo |
| `sdt_compressed` | `BOOLEAN` | True if this record survived SDT (was significant) |
| `compression_ratio` | `DOUBLE` | Running ratio of raw-to-compressed events per tag |

### 4.2 Silver table: `agl_demo.ot.aggregated_tags`

| Column | Type | Description |
|---|---|---|
| `window_start` | `TIMESTAMP` | Aggregation window start |
| `window_end` | `TIMESTAMP` | Aggregation window end |
| `asset_id` | `STRING` | Asset identifier |
| `tag_name` | `STRING` | Tag path |
| `avg_value` | `DOUBLE` | Mean value in window |
| `min_value` | `DOUBLE` | Min value in window |
| `max_value` | `DOUBLE` | Max value in window |
| `stddev_value` | `DOUBLE` | Std deviation in window |
| `sample_count` | `INT` | Raw samples in window |
| `compressed_count` | `INT` | Post-SDT samples in window |

### 4.3 Metrics table: `agl_demo.ot.ingest_metrics`

| Column | Type | Description |
|---|---|---|
| `window_start` | `TIMESTAMP` | 5-second window start |
| `window_end` | `TIMESTAMP` | 5-second window end |
| `records_raw` | `LONG` | Records generated before SDT |
| `records_after_sdt` | `LONG` | Records that survived SDT compression |
| `bytes_estimate` | `LONG` | Approximate bytes written to Delta |
| `avg_latency_ms` | `DOUBLE` | Avg (ingest_timestamp - event_timestamp) in ms |
| `p99_latency_ms` | `DOUBLE` | P99 latency in ms |
| `tags_active` | `LONG` | Distinct tags seen in window |
| `sdt_compression_ratio` | `DOUBLE` | records_raw / records_after_sdt |

### 4.4 SDT configuration table: `agl_demo.ot.sdt_config`

| Column | Type | Description |
|---|---|---|
| `tag_pattern` | `STRING` | Glob pattern matching tag names (e.g., `*/temperature_c`) |
| `comp_dev` | `DOUBLE` | Compression deviation (engineering units) |
| `comp_dev_percent` | `DOUBLE` | CompDev as % of tag span (alternative to absolute) |
| `comp_max_seconds` | `INT` | Max time before forcing an archive event (like PI CompMax) |
| `comp_min_seconds` | `INT` | Min time between archived events (like PI CompMin) |

### 4.5 Asset metadata: `agl_demo.ot.assets`

| Column | Type | Description |
|---|---|---|
| `asset_id` | `STRING` | PK |
| `asset_name` | `STRING` | Display name |
| `asset_type` | `STRING` | wind_turbine / battery_bess |
| `site_name` | `STRING` | e.g., Hexham, Liddell, Tomago |
| `capacity_mw` | `DOUBLE` | Rated capacity |
| `latitude` | `DOUBLE` | For map display |
| `longitude` | `DOUBLE` | For map display |
| `commissioned_date` | `DATE` | Nullable |
| `tag_count` | `INT` | Number of tags per asset |

---

## 5 · Functional requirements

### Phase 1 — Project scaffold and data layer

**FR-001: Project structure**
The system shall create the following directory layout:
```
/
├── frontend/           # React + Vite app
│   ├── src/
│   │   ├── components/ # Reusable UI components
│   │   ├── pages/      # Route-level pages
│   │   ├── hooks/      # Custom React hooks
│   │   ├── services/   # API client functions
│   │   ├── utils/      # Helpers, formatters
│   │   └── App.jsx
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── package.json
├── backend/            # Express API server
│   ├── src/
│   │   ├── routes/     # Express route handlers
│   │   ├── services/   # Business logic + Databricks SQL queries
│   │   ├── config/     # Environment config
│   │   └── index.js
│   └── package.json
├── simulator/          # Ignition tag simulator + Zerobus publisher
│   ├── src/
│   │   ├── profiles/   # Asset tag profiles (JSON)
│   │   ├── sdt/        # Swinging Door Trending engine
│   │   ├── generator.js
│   │   └── publisher.js
│   └── package.json
├── databricks/         # SQL scripts and notebooks
│   ├── setup_tables.sql
│   ├── silver_transform.sql
│   └── metrics_view.sql
├── .env.example
├── docker-compose.yml  # Optional: for local dev
└── README.md
```

- **AC-001-1**: Running `npm install` in `/frontend`, `/backend`, and `/simulator` succeeds without errors.
- **AC-001-2**: A root `README.md` exists with setup instructions, env var list, and architecture diagram in Mermaid.

**FR-002: Environment configuration**
The system shall read all secrets and endpoints from environment variables:
- `DATABRICKS_HOST` — workspace URL
- `DATABRICKS_TOKEN` — PAT or OAuth token
- `DATABRICKS_HTTP_PATH` — SQL warehouse HTTP path
- `DATABRICKS_CATALOG` — default `agl_demo`
- `DATABRICKS_SCHEMA` — default `ot`
- `ZEROBUS_ENDPOINT` — Zerobus gRPC endpoint
- `ZEROBUS_CLIENT_ID` — OAuth client ID
- `ZEROBUS_CLIENT_SECRET` — OAuth client secret
- `ZEROBUS_TABLE` — target Delta table FQN
- `SDT_DEFAULT_COMP_DEV_PERCENT` — default SDT compression deviation as % of span (default `1.0`)
- `SDT_DEFAULT_COMP_MAX_SECONDS` — default max time between events (default `600`)

- **AC-002-1**: `.env.example` contains all variables with placeholder values and comments.
- **AC-002-2**: Missing required variables cause the app to exit with a descriptive error.

**FR-003: Databricks SQL setup scripts**
The system shall provide SQL scripts that create all tables from Section 4 in Unity Catalog.

- **AC-003-1**: `setup_tables.sql` is idempotent (`CREATE TABLE IF NOT EXISTS`).
- **AC-003-2**: Tables are created under the configurable catalog and schema.
- **AC-003-3**: `sdt_config` table is pre-populated with sensible defaults for all tag types (temperature: 0.5°C, power: 1% of span, SOC: 0.5%, etc.).

**FR-004: Backend API server**
The system shall run an Express server exposing a REST API on a configurable port (default `3001`).

- **AC-004-1**: `GET /health` returns `{ "status": "ok", "timestamp": "<ISO>" }`.
- **AC-004-2**: All Databricks queries use the official `@databricks/sql` Node.js connector.
- **AC-004-3**: CORS is enabled for `localhost:5173` (Vite dev) and configurable origins.

**FR-005: Frontend scaffold**
The system shall create a React + Vite app with Tailwind CSS, a sidebar navigation, and placeholder pages.

- **AC-005-1**: `npm run dev` starts the frontend on port `5173`.
- **AC-005-2**: Navigation includes links: Dashboard, Assets, Asset Detail, Compression, Architecture.
- **AC-005-3**: A dark-themed design system is applied (suitable for control-room aesthetic).

---

### Phase 2 — Ignition simulator and Zerobus integration (with SDT)

**FR-006: Asset tag profiles**
The system shall define JSON profiles for simulated assets with realistic AGL-like tags.

Wind turbine profile (per turbine):
- `generator/speed_rpm`, `generator/power_kw`, `generator/torque_nm`
- `rotor/blade_pitch_deg`, `rotor/wind_speed_ms`, `rotor/rotor_rpm`
- `nacelle/yaw_angle_deg`, `nacelle/temperature_c`
- `grid/voltage_v`, `grid/frequency_hz`, `grid/reactive_power_kvar`
- `status/operational_state`, `status/alarm_code`

Battery BESS profile (per unit):
- `battery/soc_pct`, `battery/soh_pct`, `battery/voltage_v`, `battery/current_a`
- `battery/temperature_c`, `battery/charge_rate_kw`, `battery/discharge_rate_kw`
- `inverter/power_kw`, `inverter/frequency_hz`, `inverter/efficiency_pct`
- `thermal/coolant_temp_c`, `thermal/ambient_temp_c`
- `status/operational_state`, `status/alarm_code`

Each tag profile entry must include:
- `comp_dev`: default SDT compression deviation in engineering units
- `comp_dev_percent`: alternative as % of span
- `comp_max_seconds`: max archive interval
- `comp_min_seconds`: min archive interval

- **AC-006-1**: Profiles are stored as JSON files in `/simulator/src/profiles/`.
- **AC-006-2**: Each profile lists tag name, unit, min, max, typical value, noise factor, update frequency, and SDT parameters.

**FR-007: Tag value simulator**
The system shall generate realistic time-series values for each tag using configurable patterns:
- Sinusoidal with noise (e.g., wind speed, RPM)
- Step function with drift (e.g., SOC charge/discharge cycles)
- Random walk within bounds (e.g., temperature)
- Occasional alarm spikes

- **AC-007-1**: Simulator generates values at configurable intervals (default 1s per tag).
- **AC-007-2**: Generated values stay within profile-defined min/max bounds.
- **AC-007-3**: Simulator accepts CLI args: `--assets <count>` (default 20), `--interval <ms>` (default 1000), `--scenario <wind|battery|mixed>`.

**FR-028: Swinging Door Trending (SDT) engine**
The system shall implement the Swinging Door Trending compression algorithm in the simulator/connector layer, matching common historian compression semantics:

**Algorithm:**
1. When a new value arrives for a tag, compute slopes from the last archived point to the new value ± CompDev.
2. Maintain running `slope_max` and `slope_min` (the "swinging doors").
3. If the new value's slopes cause `slope_min > slope_max`, the doors have "crossed" — archive the *previous* value and reset.
4. If `CompMax` seconds elapse since last archive, force-archive the current value.
5. If less than `CompMin` seconds since last archive, skip (don't archive).

**Configuration:** SDT parameters are read from tag profiles (FR-006) and can be overridden per tag pattern via `sdt_config` table or environment defaults.

- **AC-028-1**: SDT engine is implemented as a standalone module in `/simulator/src/sdt/swinging-door.js` (or `.ts`).
- **AC-028-2**: Module exports a class `SwingingDoorCompressor` with methods: `constructor(compDev, compMax, compMin)`, `process(timestamp, value) → { archive: boolean, archivedValue?: ... }`.
- **AC-028-3**: Unit tests in `/simulator/src/sdt/swinging-door.test.js` verify:
  - Linear ramp within CompDev is compressed to 2 points (start + end).
  - Step change is immediately archived.
  - CompMax forces an archive after timeout.
  - CompMin suppresses rapid changes.
- **AC-028-4**: Publisher (FR-008) runs every raw event through the SDT engine before sending to Zerobus.
- **AC-028-5**: Publisher logs both raw event count and post-SDT event count per interval, so the UI can show compression ratio.

**FR-008: Zerobus publisher**
The system shall publish SDT-compressed tag events to Zerobus Ingest using the Zerobus JS SDK.

- **AC-008-1**: Each record matches the `raw_tags` schema exactly, including `sdt_compressed=true` and `compression_ratio`.
- **AC-008-2**: Publisher logs throughput (raw events/sec, compressed events/sec, ratio) and errors to stdout every 10 seconds.
- **AC-008-3**: Publisher handles Zerobus transient failures with automatic retry (SDK built-in).
- **AC-008-4**: Publisher supports `--streams <count>` flag to open multiple Zerobus streams for higher throughput.
- **AC-008-5**: Only events that survive SDT compression are sent to Zerobus (reducing network and ingest load).

**FR-009: Scale extrapolation logic**
The system shall compute and display extrapolated scale metrics:
- If simulating N assets × M tags at frequency F, calculate theoretical tags/sec for 2M+ total tags.
- Factor in SDT compression ratio: show both raw tag rate and effective (post-compression) ingest rate.
- Display actual (demo) vs projected (production) throughput in the UI.

- **AC-009-1**: Extrapolation formula is documented in code comments.
- **AC-009-2**: UI clearly labels "Demo (actual)" vs "Projected @ 2M tags" with and without SDT compression.

---

### Phase 3 — Node.js frontend: live dashboards

**FR-010: Dashboard page — Throughput metrics**
The system shall display a real-time throughput panel showing:
- Raw events generated/sec (line chart, rolling 5-minute window, updating every 5s)
- Post-SDT events ingested/sec (overlaid on same chart — shows compression gap)
- MB/second (line chart)
- Active tags count (big number card)
- Active assets count (big number card)
- Live SDT compression ratio (big number card, e.g., "6.2:1")

- **AC-010-1**: Data is fetched from `GET /api/metrics/throughput` which queries `ingest_metrics`.
- **AC-010-2**: Charts auto-refresh every 5 seconds without full page reload.
- **AC-010-3**: Big number cards show both actual and extrapolated values (FR-009).
- **AC-010-4**: The gap between raw and post-SDT lines is shaded to visually emphasize compression.

**FR-011: Dashboard page — Latency metrics**
The system shall display latency metrics:
- Average end-to-end latency (big number, green if <5s, amber if <10s, red if ≥10s)
- P99 latency (big number)
- Latency distribution histogram (last 5 minutes)

- **AC-011-1**: Latency = `ingest_timestamp - event_timestamp` in milliseconds.
- **AC-011-2**: Data sourced from `GET /api/metrics/latency`.

**FR-012: Dashboard page — Live event stream**
The system shall show a scrolling live feed of the latest 50 tag events (table format):
- Columns: Timestamp, Asset, Tag, Value, Quality, Latency, SDT (✓/✗ indicating if it passed compression)

- **AC-012-1**: Feed updates via polling every 2 seconds from `GET /api/events/latest?limit=50`.
- **AC-012-2**: New rows animate in with a subtle highlight.

**FR-013: Asset overview page — Map/Grid view**
The system shall display all simulated assets in a grid (or map if coordinates provided):
- Each asset card shows: name, type icon, site, status (OK/Warning/Alarm), last update time, tag count, per-asset compression ratio.
- Status derived from latest `status/alarm_code` and `status/operational_state` tags.

- **AC-013-1**: Data from `GET /api/assets` joining `assets` and latest `raw_tags`.
- **AC-013-2**: Clicking an asset card navigates to the Asset Detail page.
- **AC-013-3**: Grid supports filter by asset type (wind/battery/all).

**FR-014: Asset detail page — Tag trends**
The system shall display a detail page for a single asset showing:
- Asset metadata header (name, type, site, capacity, tag count)
- Live trend charts for 4-6 key tags (configurable per asset type)
- For wind: `generator/power_kw`, `rotor/wind_speed_ms`, `nacelle/temperature_c`, `grid/frequency_hz`
- For battery: `battery/soc_pct`, `battery/charge_rate_kw`, `battery/temperature_c`, `inverter/power_kw`
- Time range selector: Last 5 min, 15 min, 1 hour
- Option to overlay "raw" (pre-SDT) vs "archived" (post-SDT) data points to visually show what compression removes

- **AC-014-1**: Data from `GET /api/assets/:assetId/tags?tags=<list>&range=<minutes>`.
- **AC-014-2**: Charts render smoothly with at least 60 data points per trend line.
- **AC-014-3**: Page title includes asset name and site.
- **AC-014-4**: Raw vs compressed overlay toggle works and clearly shows removed points in grey/faded.

**FR-015: Asset detail page — Tag table**
The system shall show a full tag table for the selected asset:
- Columns: Tag Name, Current Value, Unit, Quality, Last Updated, CompDev, Compression Ratio, Sparkline (last 20 values)

- **AC-015-1**: Table is sortable by tag name and last updated.
- **AC-015-2**: Quality values display as human-readable labels (Good/Bad/Uncertain).
- **AC-015-3**: CompDev column shows the active SDT setting for that tag.

**FR-016: Backend API endpoints**
The system shall implement the following REST endpoints:

| Method | Path | Description |
|---|---|---|
| GET | `/api/metrics/throughput` | Throughput time-series from `ingest_metrics` (raw + post-SDT) |
| GET | `/api/metrics/latency` | Latency stats from `ingest_metrics` |
| GET | `/api/metrics/compression` | Current SDT compression ratios per asset and overall |
| GET | `/api/events/latest` | Latest N raw tag events |
| GET | `/api/assets` | All assets with current status |
| GET | `/api/assets/:id` | Single asset metadata |
| GET | `/api/assets/:id/tags` | Tag history for an asset |
| GET | `/api/compression/comparison` | Storage comparison data (FR-018) |
| GET | `/api/compression/sdt-config` | Current SDT config per tag pattern |
| PUT | `/api/compression/sdt-config` | Update SDT config (adjust CompDev live) |
| GET | `/api/config/scenario` | Current active scenario |
| POST | `/api/config/scenario` | Switch scenario |

- **AC-016-1**: All endpoints return JSON with consistent envelope: `{ data: ..., meta: { timestamp, query_time_ms } }`.
- **AC-016-2**: Errors return `{ error: { code, message } }` with appropriate HTTP status.
- **AC-016-3**: All queries include timing measurement in response metadata.

**FR-017: API query layer**
The system shall use parameterized queries via `@databricks/sql` with connection pooling.

- **AC-017-1**: No string-interpolated SQL; all dynamic values use parameter binding.
- **AC-017-2**: Connection is established on server start and reused across requests.

---

### Phase 4 — Compression view and architecture comparison

**FR-018: Compression comparison page**
The system shall show a multi-layer compression breakdown:

| Layer | What it does | Metric shown |
|---|---|---|
| Raw (no compression) | All samples at source frequency | Baseline event count and size |
| After SDT (connector) | Swinging Door Trending applied | Event count, ratio vs raw |
| After Delta columnar | Delta Parquet encoding on post-SDT data | File size, ratio vs raw bytes |
| Combined effective | End-to-end | Total compression ratio |

- **AC-018-1**: Displayed as a waterfall/funnel chart showing data volume shrinking through each layer.
- **AC-018-2**: Includes a callout: "Other platforms apply Swinging Door compression at the archive. We apply the **same algorithm** at the Zerobus connector — plus Delta columnar encoding on top. Same compression, open format, fewer moving parts."
- **AC-018-3**: Data sourced from `GET /api/compression/comparison` which aggregates from `ingest_metrics`.

**FR-019: Interactive SDT tuning panel**
The system shall let the presenter adjust SDT compression parameters live and see the impact:
- Slider for global CompDev % (0.1% to 5% of span)
- Slider for CompMax (60s to 3600s)
- "Apply" button that updates `sdt_config` and restarts affected simulator SDT engines via `PUT /api/compression/sdt-config`
- Before/after comparison: show compression ratio at old vs new settings

- **AC-019-1**: Adjusting the slider and clicking Apply changes the live compression ratio within 30 seconds.
- **AC-019-2**: Panel shows a mini trend chart demonstrating the visual difference (more aggressive compression = fewer points but same shape).
- **AC-019-3**: Includes a tooltip explaining: "CompDev = Compression Deviation. This is the maximum allowed deviation from a linear interpolation between archived points. Common CompDev parameter in historian platforms."

**FR-020: Architecture comparison page**
The system shall display a visual "Before vs After" architecture diagram:

**Before (current state):**
SCADA → Interface (exception) → Buffer → Server (swinging door compression) → Archive → ETL → Data Warehouse → BI

**After (lakehouse):**
Ignition (exception) → Zerobus Connector (swinging door compression) → Zerobus Ingest → Delta Lake (columnar compression) → SQL/ML/BI

- **AC-020-1**: Diagrams rendered as styled HTML/SVG (not images), with component counts, estimated maintenance effort, and points of failure highlighted.
- **AC-020-2**: "After" diagram highlights: "No Kafka", "No Buffer Nodes", "No Archive Servers", "Open Format".
- **AC-020-3**: Compression layers are visually annotated on both diagrams, showing that the same SDT algorithm is in both — but our stack has fewer components.

**FR-021: Operational overhead comparison**
The system shall display a comparison table:

| Dimension | Traditional stack | Databricks + Zerobus |
|---|---|---|
| Components to manage | Interface, Buffer, Server, Archive, AF, Vision, SQL access | Ignition, Zerobus Connector (serverless), Delta Tables |
| Compression algorithm | Swinging Door Trending (archive) | Swinging Door Trending (connector) + Delta columnar |
| Compression config | Per-tag in AF, proprietary tooling | Per-tag-pattern in config table, SQL-editable |
| New site onboarding | Weeks (provision infra per site) | Hours (configure tags, point at Zerobus) |
| Scaling model | Vertical (bigger servers) | Horizontal (add Zerobus streams) |
| Data format | Proprietary | Open (Delta / Parquet) |
| Query access | Proprietary SDK only | SQL, Python, Spark, REST, any Parquet reader |
| Licensing | Per-tag, per-server | Platform-level (compute-based) |

- **AC-021-1**: Table is rendered in the Architecture page below the diagrams.

**FR-022: Silver aggregation transform SQL**
The system shall provide a SQL script that creates `aggregated_tags` from `raw_tags`:
- Window-based aggregation (configurable: 1min, 5min, 15min, 1hr)
- Compute avg, min, max, stddev per tag per window
- Track `sample_count` (raw) vs `compressed_count` (post-SDT) per window

- **AC-022-1**: Script is in `/databricks/silver_transform.sql`.
- **AC-022-2**: Can be run as a scheduled Databricks SQL query or Workflow task.

---

### Phase 5 — Polish, scenarios, and demo readiness

**FR-023: Scenario switcher**
The system shall support switching between demo scenarios from the UI:
- "Wind Farm (Hexham)" — 50 turbines, wind-profile tags
- "Battery Site (Liddell)" — 20 battery units, BESS-profile tags
- "Mixed Fleet" — 30 turbines + 15 battery units

- **AC-023-1**: Switching scenario restarts the simulator with new parameters via `POST /api/config/scenario`.
- **AC-023-2**: UI shows active scenario name in the header/nav.

**FR-024: Demo reset capability**
The system shall provide a reset function that truncates demo tables and restarts the simulator cleanly.

- **AC-024-1**: Triggered via `POST /api/admin/reset` (protected by simple API key).
- **AC-024-2**: Frontend shows a confirmation dialog before reset.

**FR-025: Responsive and presentation-ready UI**
The system shall look polished on a 1080p or 4K projector screen.

- **AC-025-1**: Dashboard is usable at 1920x1080 without horizontal scroll.
- **AC-025-2**: All number displays use locale-appropriate formatting (commas, 2 decimal places).
- **AC-025-3**: Color scheme uses a dark theme with accent colors: electric blue (#3B82F6), green (#10B981), amber (#F59E0B), red (#EF4444).

**FR-026: Loading and error states**
The system shall handle data loading and error conditions gracefully.

- **AC-026-1**: All data-fetching components show skeleton loaders while loading.
- **AC-026-2**: API errors display a toast notification with the error message.
- **AC-026-3**: If the Databricks connection is unavailable, the dashboard shows a clear "Connection Lost" banner.

**FR-027: Start script and documentation**
The system shall include a one-command demo start:

```bash
# Start everything
npm run demo:start
```

This should:
1. Verify `.env` is configured.
2. Start the backend server.
3. Start the frontend dev server.
4. Start the simulator with the default scenario (SDT compression enabled).

- **AC-027-1**: `npm run demo:start` works from the repo root using `concurrently` or similar.
- **AC-027-2**: `README.md` includes: prerequisites, setup steps, env config, architecture diagram, SDT compression explanation, screenshots placeholder, and troubleshooting section.

---

## 6 · Non-functional requirements

**NFR-001: Latency**
End-to-end latency from simulated tag event to Delta table must be ≤5 seconds median under demo load, consistent with Zerobus benchmarks.

**NFR-002: Throughput**
The demo must sustain at least 1,000 raw records/sec through the SDT engine and Zerobus without back-pressure or dropped records.

**NFR-003: Security**
No secrets shall be committed to the repository. All credentials via environment variables.

**NFR-004: Idempotency**
Table creation and silver transforms must be idempotent. Re-running setup scripts shall not error or duplicate data structures.

**NFR-005: Region compatibility**
Zerobus endpoint must target `australiaeast` (Azure) for AGL demo, which is a supported region.

**NFR-006: No real AGL data**
All data is synthetic. Asset names resemble real AGL sites (Hexham, Liddell, Tomago, Bayswater) but contain only simulated values.

**NFR-007: SDT correctness**
The Swinging Door Trending implementation must produce identical compression decisions to the standard algorithm for the same input sequence and CompDev/CompMax/CompMin settings. Unit tests must verify this against known reference sequences.

---

## 7 · Demo narrative (for presenter reference)

This section is NOT code — it is a guide for the person presenting.

1. **Open** (2 min): "John, you told us the lakehouse should be the standard. We agree. Let's show you how — including the same compression semantics you may already rely on."
2. **Architecture** (2 min): Show the Before/After page. Highlight that the **same Swinging Door algorithm** runs in both stacks — but ours has fewer boxes, open format, and adds Delta columnar on top.
3. **Live ingest** (3 min): Switch to Dashboard. Show the two throughput lines — raw vs post-SDT. "See that gap? That's your compression happening in real time, at the connector, before data even hits Zerobus." Show latency staying under 5 seconds.
4. **Compression deep-dive** (3 min): Navigate to Compression page. Show the waterfall: raw → SDT → Delta columnar. Adjust CompDev slider live. "You want tighter compression? Slide it up. Looser? Slide down. Just like tuning CompDev in PI — but via SQL config, not PI System Management Tools."
5. **Asset drill-down** (3 min): Click into a Hexham wind turbine. Toggle "raw vs compressed" overlay on a trend. "These grey dots are what SDT filtered out. The blue line is what's stored. Same fidelity, fraction of the volume."
6. **Scale story** (2 min): Point to "Projected @ 2M tags" numbers. "Each Zerobus stream handles 15K rows/sec. With SDT at 6:1 compression, your effective capacity per stream is 90K raw tags/sec. 25 streams covers your entire fleet."
7. **Close** (1 min): "Same compression algorithm. Open format. No operational overhead. Every asset."

---

## 8 · Constraints and assumptions

- Zerobus Ingest is in **Public Preview** — throughput caps at 100 MB/s and 15,000 rows/s per stream.
- The connector branch (`agl-demo`) already contains partial SDT implementation — the simulator must implement a matching version for demo purposes.
- The demo assumes Azure Databricks with Unity Catalog and a SQL Warehouse for query serving.
- Node.js frontend queries Databricks SQL warehouse via REST/ODBC, not direct Delta file access.
- SDT implementation is based on the published swinging door algorithm — not a proprietary implementation.

---

## 9 · Loop instructions for Claude Code

1. Read this entire PRD before writing any code.
2. Implement phases in order (Phase 1 → 2 → 3 → 4 → 5).
3. After completing each phase, verify all `AC-*` criteria for that phase.
4. If a requirement is ambiguous, make a reasonable decision and document it in a code comment.
5. Use TypeScript or JSDoc for type safety where practical.
6. Write clean, production-quality code — this will be shown to a customer executive.
7. The SDT engine (FR-028) is a critical differentiator — implement it carefully with thorough tests.
8. Do NOT skip acceptance criteria. Each one matters.
9. When all `FR-*` and `NFR-*` are implemented and all `AC-*` pass: output `<promise>DONE</promise>`.
