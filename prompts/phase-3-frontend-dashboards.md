# Task: Phase 3 - Frontend live dashboards and backend API

## Objective

Build the live dashboard pages and all backend API endpoints that power them. This phase produces FR-010 through FR-017 from the master PRD. The frontend should be a polished, dark-themed control room UI with real-time data visualization.

## Context

Read these files to understand the current state:
- `PRD.md` - Full product requirements (Section 4 for data model, Section 5 Phase 3 for requirements)
- `CLAUDE.md` - Project conventions
- `frontend/src/` - Existing frontend scaffold from Phase 1
- `backend/src/` - Existing backend from Phase 1
- `databricks/setup_tables.sql` - Table schemas for query reference
- `progress.txt` - Learnings from previous iterations (READ THIS FIRST)

Check what Phases 1-2 built:
```bash
git log --oneline -15
ls -la frontend/src/pages/ frontend/src/components/ backend/src/routes/
```

## Technical constraints

- **Frontend**: React 18 + Vite + Tailwind CSS + TypeScript + Recharts (or Tremor) for charts
- **Backend**: Express + TypeScript + `@databricks/sql` connector
- **Parameterized queries only**: No string-interpolated SQL (FR-017, NFR security)
- **Do NOT touch `module/` or `simulator/src/sdt/`** - those are complete
- **Do NOT break Phase 1-2 gates** - all existing tests must continue to pass
- **Mock Databricks responses in tests** - tests must not require a live Databricks connection
- **Auto-refresh**: Charts update every 2-5 seconds via polling, not full page reload

## Requirements

### FR-010: Dashboard - Throughput metrics
Real-time throughput panel:
- Raw events/sec line chart (rolling 5-min window, refresh every 5s)
- Post-SDT events/sec overlaid on same chart (shows compression gap)
- Shaded area between raw and post-SDT lines
- MB/second line chart
- Big number cards: active tags, active assets, live SDT compression ratio

Acceptance criteria:
- Data from `GET /api/metrics/throughput` querying `ingest_metrics` table
- Charts auto-refresh every 5 seconds
- Big number cards show actual and extrapolated values
- Gap between raw/post-SDT lines is shaded

### FR-011: Dashboard - Latency metrics
- Avg end-to-end latency (big number: green <5s, amber <10s, red >=10s)
- P99 latency (big number)
- Latency distribution histogram (last 5 min)

Acceptance criteria:
- Latency = `ingest_timestamp - event_timestamp` in ms
- Data from `GET /api/metrics/latency`

### FR-012: Dashboard - Live event stream
Scrolling table of latest 50 events:
- Columns: Timestamp, Asset, Tag, Value, Quality, Latency, SDT (check/cross)

Acceptance criteria:
- Polls `GET /api/events/latest?limit=50` every 2 seconds
- New rows animate in with subtle highlight

### FR-013: Asset overview page
Grid of all assets:
- Each card: name, type icon, site, status, last update, tag count, compression ratio
- Status from latest alarm_code and operational_state tags

Acceptance criteria:
- Data from `GET /api/assets` joining `assets` and latest `raw_tags`
- Clicking a card navigates to Asset Detail page
- Filter by asset type (wind/battery/all)

### FR-014: Asset detail page - Tag trends
Detail page for a single asset:
- Metadata header (name, type, site, capacity, tag count)
- Live trend charts for 4-6 key tags per asset type
- Time range selector: 5 min, 15 min, 1 hour
- Toggle to overlay raw vs compressed data points

Acceptance criteria:
- Data from `GET /api/assets/:assetId/tags?tags=<list>&range=<minutes>`
- Charts render with at least 60 data points per trend
- Page title includes asset name and site
- Raw vs compressed toggle shows removed points in grey/faded

### FR-015: Asset detail page - Tag table
Full tag table for selected asset:
- Columns: Tag Name, Current Value, Unit, Quality, Last Updated, CompDev, Compression Ratio, Sparkline

Acceptance criteria:
- Sortable by tag name and last updated
- Quality displays as human-readable (Good/Bad/Uncertain)
- CompDev column shows active SDT setting

### FR-016: Backend API endpoints
Implement all REST endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/metrics/throughput` | Throughput time-series from `ingest_metrics` |
| GET | `/api/metrics/latency` | Latency stats from `ingest_metrics` |
| GET | `/api/metrics/compression` | SDT compression ratios per asset and overall |
| GET | `/api/events/latest` | Latest N raw tag events |
| GET | `/api/assets` | All assets with current status |
| GET | `/api/assets/:id` | Single asset metadata |
| GET | `/api/assets/:id/tags` | Tag history for an asset |
| GET | `/api/compression/comparison` | Storage comparison data (Phase 4) |
| GET | `/api/compression/sdt-config` | Current SDT config per tag pattern |
| PUT | `/api/compression/sdt-config` | Update SDT config |
| GET | `/api/config/scenario` | Current active scenario |
| POST | `/api/config/scenario` | Switch scenario |

Acceptance criteria:
- All endpoints return `{ data: ..., meta: { timestamp, query_time_ms } }`
- Errors return `{ error: { code, message } }` with appropriate HTTP status
- All queries include timing in response metadata

### FR-017: API query layer
Parameterized queries with connection pooling.

Acceptance criteria:
- No string-interpolated SQL - all dynamic values use parameter binding
- Connection established on server start, reused across requests

## Test plan (write these FIRST)

### Backend API tests (`backend/src/__tests__/`)

- [ ] `routes/metrics.test.ts`: GET /api/metrics/throughput returns `{ data: [...], meta: { timestamp, query_time_ms } }` shape
- [ ] `routes/metrics.test.ts`: GET /api/metrics/latency returns avg_latency_ms and p99_latency_ms fields
- [ ] `routes/metrics.test.ts`: GET /api/metrics/compression returns per-asset and overall ratios
- [ ] `routes/events.test.ts`: GET /api/events/latest returns array with limit parameter respected
- [ ] `routes/events.test.ts`: GET /api/events/latest?limit=10 returns at most 10 records
- [ ] `routes/assets.test.ts`: GET /api/assets returns array of assets with status fields
- [ ] `routes/assets.test.ts`: GET /api/assets/:id returns single asset or 404
- [ ] `routes/assets.test.ts`: GET /api/assets/:id/tags returns tag history array
- [ ] `routes/compression.test.ts`: GET /api/compression/sdt-config returns array of config entries
- [ ] `routes/compression.test.ts`: PUT /api/compression/sdt-config validates input and returns updated config
- [ ] `routes/config.test.ts`: GET /api/config/scenario returns current scenario name
- [ ] `routes/config.test.ts`: POST /api/config/scenario accepts valid scenario name
- [ ] `services/query.test.ts`: Query service uses parameterized queries (no string interpolation)
- [ ] `middleware/envelope.test.ts`: Response envelope middleware adds meta.timestamp and meta.query_time_ms
- [ ] `middleware/errors.test.ts`: Error handler returns `{ error: { code, message } }` format with correct HTTP status

### Frontend component tests (`frontend/src/__tests__/`)

- [ ] `pages/Dashboard.test.tsx`: Dashboard page renders throughput chart, latency panel, and event stream sections
- [ ] `pages/Assets.test.tsx`: Assets page renders asset grid with filter controls
- [ ] `pages/AssetDetail.test.tsx`: Asset detail page renders metadata header, trend charts, and tag table
- [ ] `components/ThroughputChart.test.tsx`: ThroughputChart component renders with mock data without crashing
- [ ] `components/BigNumberCard.test.tsx`: BigNumberCard displays value and label, applies color class based on threshold
- [ ] `components/EventStream.test.tsx`: EventStream table renders columns: Timestamp, Asset, Tag, Value, Quality, Latency, SDT
- [ ] `components/AssetCard.test.tsx`: AssetCard shows name, type, status, and is clickable
- [ ] `hooks/usePolling.test.ts`: usePolling hook calls fetch at specified interval and returns latest data

## Gates

Run `bash gates.sh` to verify all completion criteria. Same 13 gates:

| Gate | Command |
|------|---------|
| FE Install | `npm --prefix frontend install --silent` |
| BE Install | `npm --prefix backend install --silent` |
| Sim Install | `npm --prefix simulator install --silent` |
| FE Lint | `npm --prefix frontend run lint` |
| BE Lint | `npm --prefix backend run lint` |
| Sim Lint | `npm --prefix simulator run lint` |
| FE Typecheck | `npm --prefix frontend run typecheck` |
| BE Typecheck | `npm --prefix backend run typecheck` |
| Sim Typecheck | `npm --prefix simulator run typecheck` |
| FE Tests | `npm --prefix frontend run test -- --run` |
| BE Tests | `npm --prefix backend run test -- --run` |
| Sim Tests | `npm --prefix simulator run test -- --run` |
| FE Build | `npm --prefix frontend run build` |

## Completion criteria

The task is COMPLETE only when ALL of the following are true:

1. You have run `bash gates.sh` and the output shows **exactly** `13 passed, 0 failed`
2. The exit code of `bash gates.sh` is **0**
3. All 23 tests from the test plan above exist as real test files and are passing
4. All 12 API endpoints from FR-016 are implemented and return the correct envelope format
5. Dashboard page renders throughput, latency, and event stream panels
6. Assets page renders a filterable grid of asset cards
7. Asset detail page renders trends, tag table, and raw/compressed toggle
8. All Phase 1 and Phase 2 tests still pass

**You MUST verify completion mechanically.** Do NOT self-assess. Run `bash gates.sh` and read the output.

## Instructions

Follow TDD (red-green-refactor):

1. Read context files, especially `progress.txt`
2. **Red**: Write backend API route tests first (mock Databricks responses)
3. **Green**: Implement API routes, query service, response envelope middleware
4. Run `bash gates.sh` - backend gates should pass
5. **Red**: Write frontend component and page tests
6. **Green**: Implement dashboard page, assets page, asset detail page, components
7. Install Recharts (or Tremor) for chart rendering
8. Wire frontend services to call backend API endpoints
9. Run `bash gates.sh` - all 13 gates should pass
10. Commit and update `progress.txt`

## Signaling completion

When you are done, you MUST follow this exact sequence:

1. Run `bash gates.sh`
2. Read the output. Confirm it says `13 passed, 0 failed`.
3. If ANY gate shows `FAIL`, do NOT proceed - fix the issue and re-run.
4. Only after confirming all 13 gates pass, output this EXACT string on its own line:

<promise>TASK COMPLETE</promise>

### Rules about the completion signal

- You MUST run `bash gates.sh` immediately before outputting the promise. Not 5 steps before. Immediately before.
- You MUST see `13 passed, 0 failed` in the output. If you see anything else, you are NOT done.
- Do NOT output `<promise>TASK COMPLETE</promise>` if even a single gate failed.
- Do NOT output the promise based on your own judgment, memory, or belief that things work. Only the gate output matters.
- Do NOT guess, assume, or predict that gates will pass. Run them and read the result.
- Do NOT output the promise to "try to finish" or "move on". It means "all work is verified done".
- If you are stuck and cannot make all gates pass after sustained effort, do NOT output the promise. Instead, append your blockers and what you tried to `progress.txt` so the next iteration can pick up where you left off.
