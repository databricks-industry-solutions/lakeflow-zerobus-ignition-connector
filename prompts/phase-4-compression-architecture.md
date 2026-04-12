# Task: Phase 4 - Compression view and architecture comparison

## Objective

Build the compression comparison page, interactive SDT tuning panel, architecture comparison page, and silver aggregation SQL. This phase produces FR-018 through FR-022 from the master PRD. These pages are the demo's key differentiators - they prove that Databricks + Zerobus matches common historian compression while being simpler and more open.

## Context

Read these files to understand the current state:
- `PRD.md` - Full product requirements (Section 5 Phase 4, Section 7 for demo narrative)
- `CLAUDE.md` - Project conventions
- `frontend/src/pages/` - Existing pages from Phase 3
- `frontend/src/components/` - Existing components
- `backend/src/routes/` - Existing API routes
- `simulator/src/sdt/swinging-door.ts` - SDT engine from Phase 2
- `databricks/setup_tables.sql` - Table schemas
- `progress.txt` - Learnings from previous iterations (READ THIS FIRST)

Check what Phases 1-3 built:
```bash
git log --oneline -20
ls -la frontend/src/pages/ backend/src/routes/
```

## Technical constraints

- **Do NOT touch `module/`** or break existing functionality
- **Do NOT break Phase 1-3 gates** - all existing tests must continue to pass
- **Charts**: Use Recharts (or Tremor) matching Phase 3 patterns
- **SDT tuning must be live**: Adjusting compression parameters via the UI should affect the running simulator within 30 seconds
- **Mock Databricks in tests**: No live connection needed for tests
- **SQL scripts must be idempotent**

## Requirements

### FR-018: Compression comparison page
Multi-layer compression breakdown displayed as a waterfall/funnel chart:

| Layer | What it shows |
|-------|---------------|
| Raw (no compression) | Baseline event count and size |
| After SDT (connector) | Event count and ratio vs raw |
| After Delta columnar | File size and ratio vs raw bytes |
| Combined effective | Total end-to-end compression ratio |

Acceptance criteria:
- Waterfall/funnel chart showing data volume shrinking through each layer
- Includes callout text: "Other platforms apply Swinging Door compression at the archive. We apply the **same algorithm** at the Zerobus connector - plus Delta columnar encoding on top. Same compression, open format, fewer moving parts."
- Data from `GET /api/compression/comparison` aggregating `ingest_metrics`

### FR-019: Interactive SDT tuning panel
Live adjustment of SDT parameters:
- Slider for global CompDev % (0.1% to 5% of span)
- Slider for CompMax (60s to 3600s)
- "Apply" button that calls `PUT /api/compression/sdt-config`
- Before/after comparison showing compression ratio at old vs new settings
- Mini trend chart showing visual difference

Acceptance criteria:
- Adjusting slider + Apply changes live compression ratio within 30 seconds
- Mini trend demonstrates visual difference (more aggressive = fewer points, same shape)
- Tooltip explains: "CompDev = Compression Deviation. Maximum allowed deviation from linear interpolation between archived points. Common CompDev parameter in historian platforms."

### FR-020: Architecture comparison page
Visual "Before vs After" architecture diagrams:

**Before (traditional stack):** SCADA -> Interface (exception) -> Buffer -> Server (SDT) -> Archive -> ETL -> DW -> BI

**After (Lakehouse):** Ignition (exception) -> Zerobus Connector (SDT) -> Zerobus Ingest -> Delta Lake (columnar) -> SQL/ML/BI

Acceptance criteria:
- Diagrams rendered as styled HTML/SVG (not images), with component counts and failure points highlighted
- "After" highlights: "No Kafka", "No Buffer Nodes", "No Archive Servers", "Open Format"
- Compression layers visually annotated on both diagrams

### FR-021: Operational overhead comparison table

| Dimension | Other platforms | Databricks + Zerobus |
|-----------|----------|---------------------|
| Components | Interface, Buffer, Server, Archive, AF, Vision, SQL access | Ignition, Zerobus Connector (serverless), Delta Tables |
| Compression | SDT at archive | SDT at connector + Delta columnar |
| New site onboarding | Weeks | Hours |
| Scaling | Vertical | Horizontal |
| Data format | Proprietary | Open (Delta/Parquet) |
| Query access | Proprietary SDK only | SQL, Python, Spark, REST |
| Licensing | Per-tag, per-server | Platform-level |

Acceptance criteria:
- Table rendered in the Architecture page below the diagrams

### FR-022: Silver aggregation SQL
SQL script creating `aggregated_tags` from `raw_tags`:
- Window-based aggregation (1min, 5min, 15min, 1hr)
- Compute avg, min, max, stddev per tag per window
- Track sample_count (raw) vs compressed_count (post-SDT)

Acceptance criteria:
- Script in `databricks/silver_transform.sql`
- Can be run as scheduled Databricks SQL query

## Test plan (write these FIRST)

### Backend tests (`backend/src/__tests__/`)

- [ ] `routes/compression.test.ts`: GET /api/compression/comparison returns layers array with fields: layer_name, event_count, size_bytes, ratio_vs_raw
- [ ] `routes/compression.test.ts`: GET /api/compression/comparison returns exactly 4 layers (raw, after_sdt, after_delta, combined)
- [ ] `routes/compression.test.ts`: PUT /api/compression/sdt-config accepts comp_dev_percent (0.1-5.0) and comp_max_seconds (60-3600)
- [ ] `routes/compression.test.ts`: PUT /api/compression/sdt-config rejects out-of-range values with 400 status

### Frontend tests (`frontend/src/__tests__/`)

- [ ] `pages/Compression.test.tsx`: Compression page renders waterfall chart section and SDT tuning panel
- [ ] `pages/Architecture.test.tsx`: Architecture page renders before/after diagrams and comparison table
- [ ] `components/CompressionWaterfall.test.tsx`: Waterfall chart renders 4 layers with labels
- [ ] `components/CompressionWaterfall.test.tsx`: Waterfall chart includes the compression callout text
- [ ] `components/SdtTuningPanel.test.tsx`: Tuning panel renders CompDev slider (0.1-5.0 range) and CompMax slider (60-3600 range)
- [ ] `components/SdtTuningPanel.test.tsx`: Apply button calls PUT /api/compression/sdt-config with current slider values
- [ ] `components/SdtTuningPanel.test.tsx`: Tooltip with CompDev explanation is present
- [ ] `components/ArchitectureDiagram.test.tsx`: Before diagram renders traditional stack components (Interface, Buffer, Server, Archive)
- [ ] `components/ArchitectureDiagram.test.tsx`: After diagram renders Lakehouse components and highlights "No Kafka", "No Buffer Nodes", "No Archive Servers", "Open Format"
- [ ] `components/ComparisonTable.test.tsx`: Comparison table renders all 7 dimension rows

### SQL validation tests (any package)

- [ ] `sql-validation.test.ts`: `databricks/silver_transform.sql` exists and contains aggregation window logic
- [ ] `sql-validation.test.ts`: Silver transform SQL references `raw_tags` table and creates/inserts into `aggregated_tags`

## Gates

Run `bash gates.sh` to verify. Same 13 gates as previous phases.

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
3. All 16 tests from the test plan above exist as real test files and are passing
4. Compression page renders waterfall chart with 4 layers and SDT tuning panel with sliders
5. Architecture page renders before/after diagrams and 7-row comparison table
6. `databricks/silver_transform.sql` exists with window aggregation logic
7. All Phase 1, 2, and 3 tests still pass

**You MUST verify completion mechanically.** Do NOT self-assess. Run `bash gates.sh` and read the output.

## Instructions

Follow TDD (red-green-refactor):

1. Read context files, especially `progress.txt`
2. **Red**: Write backend compression route tests (comparison layers, SDT config validation)
3. **Green**: Implement the routes
4. **Red**: Write frontend component tests (waterfall, tuning panel, architecture diagrams, table)
5. **Green**: Implement the pages and components
6. Create `databricks/silver_transform.sql`
7. Write SQL validation tests
8. Run `bash gates.sh` - all 13 gates should pass
9. Commit and update `progress.txt`

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
