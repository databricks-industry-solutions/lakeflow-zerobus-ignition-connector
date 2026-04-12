# Task: Phase 2 - Ignition simulator and SDT compression engine

## Objective

Build the tag value simulator, Swinging Door Trending (SDT) compression engine, and Zerobus publisher. This phase produces FR-006 through FR-009 and FR-028 from the master PRD. The SDT engine is the critical differentiator for the AGL demo - it must be algorithmically correct and thoroughly tested.

## Context

Read these files to understand the current state:
- `PRD.md` - Full product requirements (Section 4 for data model, Section 5 Phase 2 for requirements, Section 8 for constraints)
- `CLAUDE.md` - Project conventions
- `simulator/package.json` - Current simulator package setup from Phase 1
- `simulator/src/` - Existing simulator scaffold
- `.env.example` - Environment variables including SDT defaults
- `progress.txt` - Learnings from previous iterations (READ THIS FIRST)

Check what Phase 1 built:
```bash
git log --oneline -10
ls -la simulator/src/
```

## Technical constraints

- **Language**: TypeScript (matching Phase 1 scaffold)
- **Test framework**: Vitest (matching Phase 1 scaffold)
- **SDT correctness is critical**: The Swinging Door Trending implementation must produce identical compression decisions to the standard algorithm for the same input sequence and CompDev/CompMax/CompMin settings (NFR-007)
- **Do NOT touch `module/`** - that's the Java Ignition module
- **Do NOT break Phase 1 gates** - all existing tests must continue to pass
- **Zerobus SDK**: Use `zerobus-ingest-sdk` or mock it if the JS SDK is unavailable. The publisher structure must be correct even if we can't call the real endpoint.

## Requirements

### FR-006: Asset tag profiles
JSON profiles for simulated AGL assets with realistic tags.

**Wind turbine profile** (per turbine - 13 tags):
- `generator/speed_rpm`, `generator/power_kw`, `generator/torque_nm`
- `rotor/blade_pitch_deg`, `rotor/wind_speed_ms`, `rotor/rotor_rpm`
- `nacelle/yaw_angle_deg`, `nacelle/temperature_c`
- `grid/voltage_v`, `grid/frequency_hz`, `grid/reactive_power_kvar`
- `status/operational_state`, `status/alarm_code`

**Battery BESS profile** (per unit - 13 tags):
- `battery/soc_pct`, `battery/soh_pct`, `battery/voltage_v`, `battery/current_a`
- `battery/temperature_c`, `battery/charge_rate_kw`, `battery/discharge_rate_kw`
- `inverter/power_kw`, `inverter/frequency_hz`, `inverter/efficiency_pct`
- `thermal/coolant_temp_c`, `thermal/ambient_temp_c`
- `status/operational_state`, `status/alarm_code`

Each tag entry must include: tag name, unit, min, max, typical value, noise factor, update frequency, and SDT parameters (comp_dev, comp_dev_percent, comp_max_seconds, comp_min_seconds).

Acceptance criteria:
- Profiles stored as JSON files in `simulator/src/profiles/`
- Each profile lists all required fields per tag

### FR-028: Swinging Door Trending (SDT) engine
Implement the SDT compression algorithm matching common historian semantics.

**Algorithm:**
1. When a new value arrives, compute slopes from the last archived point to the new value +/- CompDev
2. Maintain running `slope_max` and `slope_min` (the "swinging doors")
3. If new value's slopes cause `slope_min > slope_max`, doors crossed - archive the *previous* value and reset
4. If `CompMax` seconds elapse since last archive, force-archive current value
5. If less than `CompMin` seconds since last archive, skip

Acceptance criteria:
- Implemented as standalone module in `simulator/src/sdt/swinging-door.ts`
- Exports class `SwingingDoorCompressor` with: `constructor(compDev, compMax, compMin)`, `process(timestamp, value) => { archive: boolean, archivedValue?: ... }`
- Unit tests verify all 4 core behaviors (see test plan below)

### FR-007: Tag value simulator
Generate realistic time-series values using configurable patterns:
- Sinusoidal with noise (wind speed, RPM)
- Step function with drift (SOC charge/discharge cycles)
- Random walk within bounds (temperature)
- Occasional alarm spikes

Acceptance criteria:
- Generates values at configurable intervals (default 1s per tag)
- Values stay within profile-defined min/max bounds
- Accepts CLI args: `--assets <count>` (default 20), `--interval <ms>` (default 1000), `--scenario <wind|battery|mixed>`

### FR-008: Zerobus publisher
Publish SDT-compressed tag events to Zerobus Ingest.

Acceptance criteria:
- Each record matches `raw_tags` schema exactly, including `sdt_compressed=true` and `compression_ratio`
- Logs throughput (raw events/sec, compressed events/sec, ratio) every 10 seconds
- Handles transient failures with retry
- Supports `--streams <count>` flag
- Only events surviving SDT compression are sent

### FR-009: Scale extrapolation logic
Compute projected scale metrics for 2M+ tags.

Acceptance criteria:
- Extrapolation formula documented in code comments
- Exports a function that takes (actual_assets, actual_tags_per_asset, frequency, sdt_ratio) and returns projected metrics
- UI labels distinguish "Demo (actual)" vs "Projected @ 2M tags"

## Test plan (write these FIRST)

Follow TDD - write failing tests before writing implementation code.

### SDT engine tests (`simulator/src/sdt/__tests__/swinging-door.test.ts`) - MOST IMPORTANT

- [ ] **Linear ramp within CompDev**: Feed a linear ramp of values where deviation never exceeds CompDev. Assert only 2 points are archived (start + end). This proves the algorithm compresses linear data.
- [ ] **Step change archives immediately**: Feed a constant value then a sudden large step exceeding CompDev. Assert the value before the step and the step value are both archived.
- [ ] **CompMax forces archive**: Feed values that stay within CompDev (so SDT would normally suppress them). Wait longer than CompMax seconds between values. Assert a value is force-archived after CompMax.
- [ ] **CompMin suppresses rapid changes**: Feed values that change rapidly (exceeding CompDev each time) but faster than CompMin interval. Assert values within CompMin window are suppressed.
- [ ] **Sinusoidal signal compression**: Feed a sine wave through SDT with a known CompDev. Assert compression ratio is > 1.0 (more input points than archived points).
- [ ] **First value is always archived**: Feed a single value. Assert it is archived (first value must always be stored).
- [ ] **Compression ratio tracking**: Process N values, verify the compressor reports correct ratio (raw_count / archived_count).

### Tag profile tests (`simulator/src/profiles/__tests__/profiles.test.ts`)

- [ ] **Wind profile has all required tags**: Load wind profile JSON, assert it contains all 13 tag definitions.
- [ ] **Battery profile has all required tags**: Load battery profile JSON, assert it contains all 13 tag definitions.
- [ ] **Each tag has required fields**: For every tag in every profile, assert fields exist: name, unit, min, max, typical, noise_factor, update_frequency_ms, comp_dev, comp_dev_percent, comp_max_seconds, comp_min_seconds.
- [ ] **Min < max for all tags**: Assert min < max for every numeric tag.

### Generator tests (`simulator/src/__tests__/generator.test.ts`)

- [ ] **Sinusoidal pattern stays in bounds**: Generate 100 values using sinusoidal pattern with min=0, max=100. Assert all values are in [0, 100].
- [ ] **Step function pattern produces steps**: Generate 1000 values using step pattern. Assert at least 2 distinct value plateaus exist.
- [ ] **Random walk stays in bounds**: Generate 1000 values using random walk with min=0, max=100. Assert all values are in [0, 100].
- [ ] **Generator respects interval**: Create generator with 100ms interval, collect timestamps for 5 values. Assert timestamps are ~100ms apart (within tolerance).

### Publisher tests (`simulator/src/__tests__/publisher.test.ts`)

- [ ] **Publisher produces records matching raw_tags schema**: Mock the Zerobus client. Publish one event. Assert the record has all required columns: event_timestamp, ingest_timestamp, asset_id, asset_type, tag_name, tag_value, quality, source_system, sdt_compressed, compression_ratio.
- [ ] **Publisher only sends SDT-surviving events**: Feed 100 values through publisher with SDT enabled. Assert the number of records sent to Zerobus is less than 100.
- [ ] **Publisher logs throughput**: Capture stdout during a publish cycle. Assert it contains raw count, compressed count, and ratio.

### Extrapolation tests (`simulator/src/__tests__/extrapolation.test.ts`)

- [ ] **Extrapolation formula**: Given 20 assets x 13 tags at 1s interval with 6:1 SDT ratio, assert projected raw rate for 2M tags is calculated correctly.
- [ ] **Extrapolation includes compression**: Assert projected post-SDT rate is raw_rate / sdt_ratio.

## Gates

Run `bash gates.sh` to verify all completion criteria at once. Same 13 gates as Phase 1:

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

Expected output:
```
  FE Install           ok
  BE Install           ok
  Sim Install          ok
  FE Lint              ok
  BE Lint              ok
  Sim Lint             ok
  FE Typecheck         ok
  BE Typecheck         ok
  Sim Typecheck        ok
  FE Tests             ok
  BE Tests             ok
  Sim Tests            ok
  FE Build             ok

All 13 gate(s): 13 passed, 0 failed
```

## Completion criteria

The task is COMPLETE only when ALL of the following are true:

1. You have run `bash gates.sh` and the output shows **exactly** `13 passed, 0 failed`
2. The exit code of `bash gates.sh` is **0** (not 1, not any other number)
3. All 21 tests from the test plan section above exist as real test files and are passing
4. `simulator/src/sdt/swinging-door.ts` exists and exports `SwingingDoorCompressor`
5. `simulator/src/profiles/` contains wind and battery JSON profiles with all required tags
6. `simulator/src/generator.ts` implements sinusoidal, step, random walk, and alarm patterns
7. `simulator/src/publisher.ts` implements Zerobus publishing with SDT filtering
8. Phase 1 tests still pass (frontend and backend gates are green)

**You MUST verify completion mechanically.** Do NOT self-assess. Do NOT assume gates pass. Run the command and read the output.

## Instructions

Follow TDD (red-green-refactor):

1. Read the context files listed above, especially `progress.txt`
2. **Red**: Write the SDT engine tests first (`swinging-door.test.ts`) - these are the most important
3. **Green**: Implement `SwingingDoorCompressor` to make SDT tests pass
4. Run `bash gates.sh` to verify simulator gates pass
5. **Red**: Write profile tests, then create the JSON profiles
6. **Red**: Write generator tests, then implement the generator
7. **Red**: Write publisher tests, then implement the publisher
8. **Red**: Write extrapolation tests, then implement the module
9. Run `bash gates.sh` - all 13 gates should pass
10. Commit working changes with clear messages
11. Append to `progress.txt` what you learned this iteration

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
