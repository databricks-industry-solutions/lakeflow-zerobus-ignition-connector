# Task: Phase 7 - SDP analytics pipeline (health scoring + revenue-at-risk)

## Objective

Build a Python analytics package with Spark Declarative Pipeline (SDP) definitions that transform Zerobus Bronze tag data into health scores and revenue-at-risk analytics. The analytics functions (z-score anomaly detection, revenue computation, market data generation) must be testable locally with pytest. The SDP pipeline definitions use `@dp.table()` / `@dp.view()` decorators and run in Databricks serverless compute.

This is the data backbone for the AGL Revenue-at-Risk Monitor app described in `APP-PRD.md`.

## Context

Read these files to understand the current state:
- `APP-PRD.md` - The app that will consume these analytics tables (health_scores, revenue_risk, nem_prices, price_forecast)
- `PRD.md` - Base demo requirements (Zerobus ingest pipeline that populates Bronze tables)
- `pipelines/sql/setup_tables.sql` - Existing table schemas (raw_tags, aggregated_tags, ingest_metrics, sdt_config, assets)
- `pipelines/sql/silver_transform.sql` - Existing manual Silver transform (MERGE-based, to be replaced by SDP streaming table)
- `CLAUDE.md` - Project conventions and build commands
- `progress.txt` - Learnings from previous iterations

Also read `progress.txt` if it exists - it contains learnings from previous iterations.

**Reference implementation** for SDP patterns and NEM data:
```bash
# Check the NEM analytics repo for SDP patterns (read-only reference)
ls /Users/david.okeeffe/Repos/australian-energy-nemweb-analytics/resources/open_electricity_pipeline/transformations/
cat /Users/david.okeeffe/Repos/australian-energy-nemweb-analytics/resources/open_electricity_pipeline/transformations/bronze_nemweb_dispatch_price.py
cat /Users/david.okeeffe/Repos/australian-energy-nemweb-analytics/resources/open_electricity_pipeline/transformations/silver_nemweb_dispatch_price.py
cat /Users/david.okeeffe/Repos/australian-energy-nemweb-analytics/resources/open_electricity_pipeline/transformations/gold_nemweb_dispatch_price_30min.py
cat /Users/david.okeeffe/Repos/australian-energy-nemweb-analytics/resources/open_electricity_pipeline/transformations/dlt_config.py
```

Check recent changes:
```bash
git log --oneline -10
```

## Technical constraints

- **SDP module**: Use `databricks.pipelines` (`dp`) - the current SDP SDK. Do NOT use the legacy `dlt` module. Look up the SDP skill or Databricks docs for current syntax.
- **Testable locally**: Analytics functions (health scoring, revenue computation, market data generation) must be pure Python - no PySpark or Spark dependencies. They take simple inputs (dicts, lists, floats) and return simple outputs. This lets pytest run without a Spark session.
- **SDP definitions separate**: The SDP pipeline files (`@dp.table()`) import the analytics functions and wrap them in Spark SQL/DataFrame logic. These files cannot be tested locally (they need Databricks runtime) but must pass ruff lint/format checks.
- **Market data is lightweight**: Seed NEM prices with a synthetic generator function, not a full NEMWEB integration. Generate realistic patterns (low overnight, afternoon peaks, occasional spikes).
- **Target catalog/schemas**: `agl_demo.ot` (existing), `agl_demo.market` (new), `agl_demo.analytics` (new).
- **Python packaging**: Use `pyproject.toml` with `ruff` and `pytest` as dev dependencies. Project root is `pipelines/sdp/`.
- **No changes to demo app**: This PRD only creates the Python analytics package and SDP pipeline definitions. The demo frontend/backend in `demo/` is untouched.

## Requirements

### FR-200: Python project scaffold
Create a Python package at `pipelines/sdp/` with:
```
pipelines/sdp/
  pyproject.toml          # Package config with [dev] extras (ruff, pytest)
  src/
    agl_analytics/
      __init__.py
      health.py           # z-score anomaly detection, health scoring
      revenue.py          # Revenue-at-risk computation
      market.py           # Synthetic NEM price generation + forecast
      schemas.py          # Table schema definitions as typed dicts / dataclasses
  tests/
    __init__.py
    conftest.py           # Shared fixtures (sample assets, sample tags, etc.)
    test_health.py
    test_revenue.py
    test_market.py
    test_schemas.py
  transformations/        # SDP pipeline definitions (run in Databricks)
    bronze_silver.py      # raw_tags -> aggregated_tags streaming table
    silver_analytics.py   # aggregated_tags -> health_scores materialized view
    market_data.py        # nem_prices + price_forecast tables
    revenue_risk.py       # health_scores + price_forecast -> revenue_risk view
```

- `pyproject.toml` includes: ruff, pytest as dev deps. numpy for z-score computation.
- `ruff` config: line-length 120, target Python 3.11+.

### FR-201: Health scoring module (`health.py`)
Implement z-score based anomaly detection per APP-PRD.md FR-105:

Functions:
- `compute_zscore(value: float, mean: float, stddev: float) -> float` - Returns z-score. If stddev is 0, return 0.0.
- `is_anomalous(zscore: float, threshold: float = 2.0) -> bool` - True if abs(zscore) > threshold.
- `compute_health_score(anomalous_count: int, total_tag_count: int) -> float` - Returns `1.0 - (anomalous_count / total_tag_count)`, clamped to [0.0, 1.0].
- `identify_primary_risk_tag(tag_zscores: dict[str, float]) -> tuple[str, float]` - Returns (tag_name, zscore) with highest abs(zscore).
- `generate_risk_description(primary_tag: str, zscore: float, current_value: float, expected_range: tuple[float, float]) -> str` - Human-readable string.
- `get_key_tags(asset_type: str) -> list[str]` - Returns key monitoring tags per asset type.
  - Wind: `nacelle/temperature_c`, `generator/power_kw`, `grid/frequency_hz`, `rotor/wind_speed_ms`
  - Battery: `battery/temperature_c`, `battery/soc_pct`, `thermal/coolant_temp_c`, `inverter/efficiency_pct`

### FR-202: Revenue-at-risk module (`revenue.py`)
Implement revenue-at-risk computation per APP-PRD.md FR-109:

Functions:
- `compute_trip_probability(health_score: float) -> float` - Returns `1.0 - health_score`, clamped to [0.0, 1.0].
- `compute_revenue_at_risk(capacity_mw: float, window_hours: float, forecast_price_aud_mwh: float, trip_probability: float) -> float` - Returns `capacity_mw * window_hours * forecast_price_aud_mwh * trip_probability`.
- `recommend_action(health_score: float, window_start: str) -> str` - Rule-based:
  - health > 0.8: "Monitor - no action needed"
  - health 0.5-0.8: "Schedule inspection before {window_start}"
  - health 0.3-0.5: "Urgent: schedule maintenance tonight"
  - health < 0.3: "Critical: consider preemptive shutdown and repair to protect fleet"
- `compute_fleet_summary(asset_risks: list[dict]) -> dict` - Aggregate: total_revenue_at_risk, assets_at_risk_count, by_site, by_asset_type.

### FR-203: Market data module (`market.py`)
Implement synthetic NEM price generation per APP-PRD.md FR-101/FR-102:

Functions:
- `generate_price_forecast(hours: int = 48, region: str = "NSW1") -> list[dict]` - Generate 5-minute interval forecasts with:
  - Base pattern: overnight $30-80, morning ramp, afternoon peak $200-500
  - 2-3 spike events per 24h during peak hours (4-7pm), prices $2,000-$15,000
  - At least one spike within next 24 hours (so demo always has urgency)
  - Each dict: `{ target_interval, region, forecast_price_aud_mwh, confidence }`
- `generate_historical_prices(days: int = 30, region: str = "NSW1") -> list[dict]` - Generate 5-minute dispatch prices following realistic NEM patterns.
  - Each dict: `{ interval_start, interval_end, region, price_aud_mwh, demand_mw }`
- `find_high_price_windows(forecast: list[dict], threshold: float = 300.0) -> list[dict]` - Identify contiguous windows where price > threshold.
  - Each dict: `{ window_start, window_end, avg_price, peak_price, duration_hours }`

### FR-204: SDP pipeline definitions (`transformations/`)
Create SDP pipeline Python files that use `@dp.table()` and `@dp.view()` decorators. These import from `agl_analytics` and define the data flow:

1. `bronze_silver.py` - Streaming table `aggregated_tags`:
   - Reads `agl_demo.ot.raw_tags` as a stream
   - 1-minute tumbling window aggregation: avg, min, max, stddev per (asset_id, tag_name)
   - Tracks sample_count and compressed_count

2. `silver_analytics.py` - Materialized view `health_scores`:
   - Reads latest 1-hour of `aggregated_tags`
   - Computes z-scores per key tag per asset
   - Writes health_score, primary_risk_tag, risk_description, anomaly_tags

3. `market_data.py` - Tables `nem_prices` and `price_forecast`:
   - `nem_prices`: Seeded from `generate_historical_prices()`, append-only
   - `price_forecast`: Regenerated from `generate_price_forecast()`, full refresh

4. `revenue_risk.py` - Materialized view `revenue_risk`:
   - Joins health_scores + price_forecast + assets
   - Computes revenue_at_risk per asset per high-price window
   - Adds recommended_action

**Important**: These files must pass `ruff check` and `ruff format --check` but they CANNOT be tested locally (they need Databricks runtime). They import from `agl_analytics` which IS tested.

### FR-205: Schema definitions (`schemas.py`)
Define expected schemas as dataclasses or TypedDicts for all output tables. These serve as documentation and test fixtures:
- `HealthScoreRecord` - matches `agl_demo.analytics.health_scores` columns from APP-PRD.md
- `RevenueRiskRecord` - matches `agl_demo.analytics.revenue_risk` columns from APP-PRD.md
- `NemPriceRecord` - matches `agl_demo.market.nem_prices` columns from APP-PRD.md
- `PriceForecastRecord` - matches `agl_demo.market.price_forecast` columns from APP-PRD.md

## Test plan (write these FIRST)

Follow TDD - write failing tests before writing implementation code.

### Tests to create

**`tests/test_health.py`** (7 tests):
- [ ] `test_zscore_normal_value` - value within 1 stddev returns abs(zscore) < 2
- [ ] `test_zscore_anomalous_value` - value > 2 stddev returns abs(zscore) > 2
- [ ] `test_zscore_zero_stddev` - stddev=0 returns zscore=0.0 (no division by zero)
- [ ] `test_health_score_all_healthy` - 0 anomalous tags, 6 total -> 1.0
- [ ] `test_health_score_all_anomalous` - 6 anomalous, 6 total -> 0.0
- [ ] `test_health_score_partial` - 2 anomalous, 6 total -> approx 0.667
- [ ] `test_primary_risk_tag_highest_zscore` - tag with highest abs(zscore) selected
- [ ] `test_key_tags_wind` - wind asset type returns 4 expected monitoring tags
- [ ] `test_key_tags_battery` - battery asset type returns 4 expected monitoring tags

**`tests/test_revenue.py`** (7 tests):
- [ ] `test_trip_probability_from_health` - trip_prob = 1 - health_score
- [ ] `test_trip_probability_clamped` - health_score > 1.0 clamps to trip_prob 0.0
- [ ] `test_revenue_at_risk_formula` - 25 MW * 2 hours * $8000/MWh * 0.7 = $280,000
- [ ] `test_revenue_at_risk_zero_probability` - healthy asset has $0 risk
- [ ] `test_recommended_action_healthy` - health 0.9 -> "Monitor"
- [ ] `test_recommended_action_warning` - health 0.6 -> "Schedule inspection"
- [ ] `test_recommended_action_urgent` - health 0.4 -> "Urgent"
- [ ] `test_recommended_action_critical` - health 0.2 -> "Critical"
- [ ] `test_fleet_summary_totals` - aggregates revenue_at_risk across 3 assets

**`tests/test_market.py`** (6 tests):
- [ ] `test_forecast_length_48h` - 48 hours * 12 intervals/hr = 576 records
- [ ] `test_forecast_has_spike_events` - at least 2 intervals > $300/MWh
- [ ] `test_forecast_overnight_low` - avg price 10pm-5am < $100/MWh
- [ ] `test_forecast_spike_in_next_24h` - at least one spike within first 24 hours
- [ ] `test_historical_prices_30_days` - 30 * 288 intervals/day = 8640 records
- [ ] `test_find_high_price_windows` - given known forecast, identifies correct windows

**`tests/test_schemas.py`** (4 tests):
- [ ] `test_health_score_schema_fields` - HealthScoreRecord has all APP-PRD columns
- [ ] `test_revenue_risk_schema_fields` - RevenueRiskRecord has all APP-PRD columns
- [ ] `test_nem_price_schema_fields` - NemPriceRecord has all APP-PRD columns
- [ ] `test_price_forecast_schema_fields` - PriceForecastRecord has all APP-PRD columns

## Gates

Run `bash gates.sh` to verify all completion criteria at once.

| Gate | Command |
|------|---------|
| Install | `$VENV/pip install -e "pipelines/sdp[dev]" --quiet` |
| Lint | `$VENV/python -m ruff check pipelines/sdp/src/ pipelines/sdp/tests/` |
| Format | `$VENV/python -m ruff format --check pipelines/sdp/src/ pipelines/sdp/tests/` |
| Tests | `$VENV/python -m pytest pipelines/sdp/tests/ -v --tb=short` |

`gates.sh` auto-creates a venv at `pipelines/sdp/.venv/` and uses its python/pip for all gates.

Output looks like:
```
  Install              ok
  Lint                 ok
  Format               ok
  Tests                ok

All 4 gate(s) passed
```

## Completion criteria

The task is COMPLETE only when:
- [ ] `bash gates.sh` exits with code 0
- [ ] All 24 tests from the test plan above are written and passing
- [ ] `pipelines/sdp/pyproject.toml` exists with ruff + pytest dev deps
- [ ] Analytics functions in `src/agl_analytics/` are pure Python (no PySpark imports)
- [ ] SDP transformation files in `transformations/` pass ruff lint/format
- [ ] Schema definitions match APP-PRD.md table columns exactly

Do NOT assess completion subjectively. Run `bash gates.sh` and check the exit code.

## Workflow

You MUST follow this exact workflow. Do NOT use EnterPlanMode or AskUserQuestion - this runs unattended.

### Step 1: Assess
Read the context files listed above, check git history, and read `progress.txt` if it exists. Check the NEM analytics reference repo for SDP patterns. Determine what has already been done in previous iterations.

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

## Important rules
- This runs UNATTENDED. Never use EnterPlanMode or AskUserQuestion.
- Do NOT declare yourself done or try to exit. The loop continues automatically.
- Each iteration: assess, plan full scope, execute ONE step, commit.
- If the task appears complete, look for improvements, edge cases, tests, or documentation to add - one at a time.
- If genuinely stuck, append your blockers to `progress.txt` for the next iteration.
- Use the `spark-declarative-pipelines` skill or Databricks docs skill to look up current SDP syntax before writing transformation files.
- The NEM analytics repo at `/Users/david.okeeffe/Repos/australian-energy-nemweb-analytics/resources/open_electricity_pipeline/transformations/` has working SDP examples - reference these for correct `@dp.table()` patterns.
