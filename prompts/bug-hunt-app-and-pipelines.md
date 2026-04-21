# Task: Find and fix bugs in the demo app and SDP pipelines

## Objective

Systematically hunt for bugs in the demo app (React frontend, FastAPI backend, simulator) and SDP ETL pipelines (Python analytics + Spark transformations). Write tests that expose each bug, then fix the code. A pre-scan has identified ~30 potential bugs across both areas - this PRD provides the inventory and TDD approach for fixing them.

## Context

Read these files to understand the current state:
- `demo/app/backend/main.py` - FastAPI app factory, SPA fallback handler
- `demo/app/backend/services/query.py` - Databricks SQL query builder (named params)
- `demo/app/backend/services/postgres_query.py` - PostgreSQL (Lakebase) query service
- `demo/app/backend/routes/compression.py` - SDT compression endpoints
- `demo/app/frontend/src/hooks/usePolling.ts` - Auto-refresh hook
- `demo/app/frontend/src/components/SdtTuningPanel.tsx` - SDT tuning visualization
- `demo/app/frontend/src/components/TreeView.tsx` - Asset tree component
- `demo/app/frontend/src/components/Sidebar.tsx` - Navigation sidebar
- `demo/app/frontend/src/pages/PostgresDashboard.tsx` - Lakebase metrics page
- `pipelines/sdp/transformations/silver_analytics.py` - Health score pipeline
- `pipelines/sdp/transformations/bronze_silver.py` - Bronze-to-silver transforms
- `pipelines/sdp/src/agl_analytics/health.py` - Z-score anomaly detection
- `pipelines/sdp/src/agl_analytics/revenue.py` - Revenue-at-risk calculations

Also read `progress.txt` if it exists - it contains learnings from previous iterations.

Check recent changes:
```bash
git log --oneline -10 -- demo/ pipelines/
```

## Technical constraints

- Do NOT modify files under `module/` (Java/Ignition code)
- Do NOT modify `Makefile`, `CLAUDE.md`, `docker/`, or `onboarding/` scripts
- Do NOT modify `releases/*.modl` files
- Keep all existing tests passing (don't break green tests)
- Follow existing code patterns and conventions
- Backend tests must run without Databricks (mark integration tests with `@pytest.mark.integration`)
- Frontend tests use Vitest + React Testing Library
- Pipeline tests use pytest + pure Python (no Spark dependency)

## Requirements

Each requirement below corresponds to a confirmed bug. Fix them in priority order.

### Critical / High severity

1. **Backend: `_asset_attr_values_update` parameter mapping corruption** (`services/query.py:717-730`)
   - The params list has 8 elements but only 6 SQL placeholders. The positional regex mapping causes `:p_value` to receive `asset_id` instead of `value`. All attribute value writes are corrupted.
   - Fix: Align the params list to match the 6 placeholders in order: `[asset_id, attribute_id, value, asset_id, attribute_id, value]`

2. **Backend: SPA fallback path traversal** (`main.py:99-105`)
   - `/{full_path:path}` handler serves any file reachable via `../` sequences. `Path(static_path) / "../../etc/passwd"` resolves outside the static directory.
   - Fix: Resolve the path and check it starts with `static_path.resolve()` before serving.

3. **Backend: asyncpg Decimal serialization** (`postgres_query.py`)
   - PostgreSQL `AVG()` / `PERCENTILE_CONT()` return `Decimal` via asyncpg. FastAPI's JSON encoder cannot serialize `Decimal`, causing 500 errors on Postgres metric endpoints.
   - Fix: Convert `Decimal` values to `float` in the query results before returning.

4. **Pipeline: `rolling_stddev` NULL not handled** (`silver_analytics.py:68`)
   - `F.stddev()` returns NULL for single-row groups. The `when` clause only checks `== 0`, not `isNull()`. Tags with one data point get NULL z-scores and are silently excluded from health scoring, inflating health scores.
   - Fix: Add `| F.col("rolling_stddev").isNull()` to the when condition.

5. **Pipeline: `F.last("avg_value")` non-deterministic** (`silver_analytics.py:39`)
   - `F.last()` in `groupBy().agg()` picks value based on physical data order, which varies between runs. Health scores are inconsistent across refreshes.
   - Fix: Use a deterministic approach like `F.max_by("avg_value", "window_start")` or add an explicit ordering.

6. **Frontend: TreeView selected text invisible** (`TreeView.tsx:86`)
   - Selected row has `text-white` on `bg-gray-100` (light gray background). Text is invisible.
   - Fix: Change to `text-blue-700` or change background to `bg-blue-600 text-white`.

7. **Frontend: Button hover text invisible** (multiple components)
   - Pattern `bg-gray-100 text-gray-700 hover:bg-gray-700` makes text invisible on hover (dark bg + dark text).
   - Affected: `AssetDetailPanel.tsx`, `ConfirmDialog.tsx`, `AssetFormModal.tsx`, `TemplateFormModal.tsx`, `AttributeFormModal.tsx`, `AssetTemplates.tsx`
   - Fix: Add `hover:text-white` or change hover bg to `hover:bg-gray-200`.

8. **Frontend: Dead sidebar link `/assets/detail`** (`Sidebar.tsx:11`)
   - Links to non-existent route. Route is `/assets/:id` but link has static path `detail`.
   - Fix: Remove the link or change to `/assets` (the overview page).

### Medium severity

9. **Backend: async pool race condition** (`postgres_query.py:76-97`)
   - Two concurrent coroutines can both create a pool when `_pool is None`, leaking the first pool.
   - Fix: Use `asyncio.Lock` to guard pool creation.

10. **Backend: Admin reset does nothing** (`routes/admin.py:20-29`)
    - Returns `"Demo tables truncated and simulator restarted"` without performing any action.
    - Fix: Either implement the reset logic or change the response to be honest (e.g., `"Reset endpoint not implemented"`).

11. **Backend: Postgres `asset_type` not mapped** (`postgres_query.py:190`)
    - DBSQL path maps `tag_provider` to friendly names (`agl_bess` -> `battery_bess`). Postgres path passes through raw values.
    - Fix: Add the same CASE/WHEN mapping in the Postgres query.

12. **Backend: Postgres `get_events_latest` missing `tag_value_str`** (`postgres_query.py:177-203`)
    - DBSQL returns `tag_value_str` via `string_value AS tag_value_str`. Postgres query omits it.
    - Fix: Add `string_value AS tag_value_str` to the Postgres SELECT.

13. **Frontend: SdtTuningPanel random data on every render** (`SdtTuningPanel.tsx:28-37`)
    - `samplePoints` uses `Math.random()` without memoization. Every slider drag regenerates random data.
    - Fix: Wrap in `useMemo` with empty deps, or use a seeded PRNG.

14. **Frontend: SdtTuningPanel props not synced to state** (`SdtTuningPanel.tsx:24-25`)
    - `useState(compDevPercent)` only uses prop as initial value. If parent re-renders with new values, sliders don't update.
    - Fix: Add `useEffect` to sync props to state when they change externally.

15. **Frontend: PostgresDashboard premature polling** (`PostgresDashboard.tsx:56`)
    - `isConfigured` defaults to `true` before health loads (`null?.status !== 'not_configured'` is `true`). Polls fire and fail.
    - Fix: Default to `false`: `const isConfigured = health != null && health.status !== 'not_configured'`

16. **Pipeline: `aggregated_tags` coalesce bug for string-only tags** (`bronze_silver.py:86-87`)
    - When both `numeric_value` and `boolean_value` are NULL, `tag_value` becomes `0.0` instead of NULL. Pollutes aggregations.
    - Fix: Add a NULL guard: only use the boolean fallback when `boolean_value IS NOT NULL`.

17. **Pipeline: `compute_fleet_summary` counts all assets as at-risk** (`revenue.py:97-101`)
    - `assets_at_risk_count` is `len(asset_risks)` regardless of actual risk. Assets with 0 risk are counted.
    - Fix: Filter to `sum(1 for a in asset_risks if a.get("revenue_at_risk_aud", 0) > 0)`

18. **Pipeline: `get_key_tags("battery_bess")` returns empty** (`health.py:144-148`)
    - Function checks `asset_type == "battery"` but pipeline uses `"battery_bess"`. Mismatch.
    - Fix: Accept both `"battery"` and `"battery_bess"`.

19. **Pipeline: Unused `pytest` import** (`tests/test_pipeline_integration.py:8`)
    - Causes ruff lint failure (F401).
    - Fix: Remove the unused import.

### Low severity (address if time permits)

20. **Backend: `convert_value` zero-as-falsy** (`query.py:878-881`) - `if val` treats numeric 0 as None
21. **Backend: `compression.py` ratio_vs_raw semantics** - name implies `layer/raw` but computes `raw/layer`
22. **Frontend: usePolling no race guard** (`usePolling.ts:29-38`) - overlapping fetches can cause stale overwrites
23. **Frontend: Compression handleApply no error handling** (`Compression.tsx:47-56`)
24. **Pipeline: `datetime.now()` local time** (`market_data.py:67`) - should use UTC
25. **Pipeline: `enriched_tags` uses FQN for pipeline-internal table** (`bronze_silver.py:186`)

## Test plan (write these FIRST)

Follow TDD - write failing tests before writing implementation code.

### Tests to create/modify

#### Backend tests (`demo/app/backend/tests/`)
- [ ] `test_query_params.py`: `test_asset_attr_values_update_param_count` - assert 6 params match 6 placeholders
- [ ] `test_query_params.py`: `test_asset_attr_values_update_param_order` - assert value goes to `:p_value` position
- [ ] `test_spa_security.py`: `test_path_traversal_blocked` - request with `../` returns 404 or 403, not file contents
- [ ] `test_spa_security.py`: `test_normal_static_file_served` - regular static files still work
- [ ] `test_postgres_unit.py`: `test_decimal_values_serializable` - verify Decimal -> float conversion
- [ ] `test_postgres_unit.py`: `test_asset_type_mapped` - verify `agl_bess` becomes `battery_bess`
- [ ] `test_postgres_unit.py`: `test_events_has_tag_value_str` - verify string_value included in events query
- [ ] `test_admin_unit.py`: `test_reset_response_is_honest` - response message matches actual behavior
- [ ] `test_compression_unit.py`: `test_ratio_vs_raw_semantics` - verify ratio direction matches field name

#### Frontend tests (`demo/app/frontend/src/__tests__/`)
- [ ] `components/TreeView.test.tsx`: `test_selected_node_text_visible` - verify no white-on-light-gray
- [ ] `components/SdtTuningPanel.test.tsx`: `test_sample_data_stable_across_renders` - re-render should keep same data
- [ ] `components/SdtTuningPanel.test.tsx`: `test_props_sync_to_state` - changing props updates sliders
- [ ] `components/Sidebar.test.tsx`: `test_no_dead_links` - all sidebar links match valid routes
- [ ] `pages/PostgresDashboard.test.tsx`: `test_no_premature_polling` - verify no API calls before health loads
- [ ] `components/ButtonHover.test.tsx`: `test_hover_text_contrast` - verify hover classes include text color

#### Pipeline tests (`pipelines/sdp/tests/`)
- [ ] `test_health.py`: `test_compute_zscore_none_stddev` - NULL stddev returns 0.0, not None
- [ ] `test_health.py`: `test_get_key_tags_battery_bess` - `"battery_bess"` returns battery tags
- [ ] `test_revenue.py`: `test_fleet_summary_excludes_zero_risk` - zero-risk assets not counted
- [ ] `test_pipeline_integration.py`: `test_aggregated_tags_null_boolean_tag_value` - verify string-only tags get NULL not 0.0

## Gates

Run `bash gates.sh` to verify all completion criteria at once. This script runs these checks:

| Gate | Command |
|------|---------|
| Frontend tests | `cd demo/app && npm test -- --run` |
| Frontend typecheck | `cd demo/app && npm run typecheck` |
| Backend tests | `cd demo/app && uv run --extra test pytest backend/tests/ -m 'not integration' -x -q` |
| Pipeline tests | `cd pipelines/sdp && uv run pytest -x -q` |
| Pipeline lint | `cd pipelines/sdp && uv run ruff check src/ tests/` |
| Simulator tests | `cd demo/simulator && npm test -- --run` |
| Simulator lint | `cd demo/simulator && npm run lint` |
| Simulator typecheck | `cd demo/simulator && npx tsc --noEmit` |

Output looks like:
```
  Frontend tests           ok
  Frontend typecheck       ok
  Backend tests            ok
  Pipeline tests           ok
  Pipeline lint            ok
  Simulator tests          ok
  Simulator lint           ok
  Simulator typecheck      ok

All 8 gate(s) passed
```

**Known baseline failure:** Pipeline lint currently FAILS (unused `pytest` import in `test_pipeline_integration.py`). This is Bug #19 and should be fixed in the first iteration.

## Completion criteria

The task is COMPLETE only when:
- [ ] `bash gates.sh` exits with code 0 (all 8 gates pass)
- [ ] All tests from the test plan above are written and passing
- [ ] Bugs #1-19 are all fixed with corresponding test coverage
- [ ] No regressions in existing tests (51 frontend + 5 backend + 65 pipeline + 36 simulator)

Do NOT assess completion subjectively. Run `bash gates.sh` and check the exit code.

## Workflow

You MUST follow this exact workflow. Do NOT use EnterPlanMode or AskUserQuestion - this runs unattended.

### Step 1: Assess
Read the context files listed above, check git history, and read `progress.txt` if it exists. Determine what has already been done in previous iterations.

### Step 2: Plan
Write out a FULL numbered implementation plan for the entire task. Number every step. Then identify which SINGLE step to tackle THIS iteration. You MUST only pick ONE step per iteration.

### Step 3: Execute ONE step
Execute ONLY the single step you identified, following TDD (red-green-refactor):

1. **Red**: Write failing tests for this ONE step
2. Run `bash gates.sh` - the test gate should fail (expected)
3. **Green**: Write the minimum code to make those tests pass
4. Run `bash gates.sh` - all gates should pass now
5. **Refactor**: Clean up while keeping gates green
6. Commit working changes with clear messages
7. Append to `progress.txt` what you learned this iteration

## Critical: scope control
- You MUST do only ONE meaningful unit of work per iteration.
- Do NOT chain multiple steps together. Stop after completing one step.
- The loop will bring you back to assess and pick the next step.
- A "step" is roughly: fix 1-3 related bugs + their tests.

## Important rules
- This runs UNATTENDED. Never use EnterPlanMode or AskUserQuestion.
- Each iteration: assess, plan full scope, execute ONE step, commit.
- If genuinely stuck, append your blockers to `progress.txt` for the next iteration.

## Loop behavior (CRITICAL - DO NOT IGNORE)

You are running in an automated loop that will restart you after each iteration. The loop stops ONLY when max iterations is reached - you CANNOT stop it early.

**NEVER DO ANY OF THESE:**
- Declare "Task Complete", "Done", "Finished", or similar
- Output completion markers or checkmarks
- Tell the user to run /cancel or stop the loop
- Output minimal responses like "OK"

**INSTEAD, when the task appears complete:**
1. Look for improvements: test coverage, edge cases, error handling
2. Review code quality: refactoring, documentation, performance
3. Update progress.txt with your assessment
4. Make meaningful improvements, one per iteration

The loop continues automatically. You cannot and should not try to exit.
