# Task: Phase 5 - Polish, scenarios, and demo readiness

## Objective

Add demo scenario switching, reset capability, responsive polish, loading/error states, and a one-command start script. This phase produces FR-023 through FR-027 from the master PRD. After this phase the demo is presentation-ready for John Bruzzaniti at AGL Energy.

## Context

Read these files to understand the current state:
- `PRD.md` - Full product requirements (Section 5 Phase 5, Section 6 for NFRs, Section 7 for demo narrative)
- `CLAUDE.md` - Project conventions
- `frontend/src/` - All frontend code from Phases 1-4
- `backend/src/` - All backend code from Phases 1-4
- `simulator/src/` - Simulator and SDT engine from Phase 2
- `progress.txt` - Learnings from previous iterations (READ THIS FIRST)

Check what Phases 1-4 built:
```bash
git log --oneline -25
ls -la frontend/src/pages/ frontend/src/components/ backend/src/routes/
```

## Technical constraints

- **Do NOT touch `module/`** or break existing functionality
- **Do NOT break Phase 1-4 gates** - all existing tests must continue to pass
- **Presentation-ready**: This will be shown on a 1080p/4K projector to a customer executive
- **Color scheme**: dark theme with electric blue (#3B82F6), green (#10B981), amber (#F59E0B), red (#EF4444)
- **No real AGL data**: All data is synthetic (NFR-006)
- **Security**: Reset endpoint protected by simple API key, no secrets in repo (NFR-003)

## Requirements

### FR-023: Scenario switcher
Switch between demo scenarios from the UI:
- "Wind Farm (Hexham)" - 50 turbines, wind-profile tags
- "Battery Site (Liddell)" - 20 battery units, BESS-profile tags
- "Mixed Fleet" - 30 turbines + 15 battery units

Acceptance criteria:
- Switching scenario restarts simulator with new parameters via `POST /api/config/scenario`
- UI shows active scenario name in header/nav
- Backend validates scenario name (only accepts: wind, battery, mixed)

### FR-024: Demo reset capability
Reset function that truncates demo tables and restarts simulator.

Acceptance criteria:
- Triggered via `POST /api/admin/reset` (protected by API key in `X-API-Key` header)
- Frontend shows confirmation dialog before reset
- Returns 401 if API key missing or wrong

### FR-025: Responsive and presentation-ready UI
Polished for 1080p or 4K projector.

Acceptance criteria:
- Dashboard usable at 1920x1080 without horizontal scroll
- All numbers use locale-appropriate formatting (commas, 2 decimal places)
- Dark theme with accent colors applied consistently across all pages

### FR-026: Loading and error states
Graceful handling of loading and errors.

Acceptance criteria:
- All data-fetching components show skeleton loaders while loading
- API errors display toast notification with error message
- Databricks connection unavailable shows "Connection Lost" banner

### FR-027: Start script and documentation
One-command demo start:

```bash
npm run demo:start
```

This should:
1. Verify `.env` is configured
2. Start backend server
3. Start frontend dev server
4. Start simulator with default scenario (SDT enabled)

Acceptance criteria:
- `npm run demo:start` works from repo root using `concurrently` or similar
- Root `README.md` includes: prerequisites, setup steps, env config, architecture diagram, SDT compression explanation, screenshots placeholder, troubleshooting section

## Test plan (write these FIRST)

### Backend tests (`backend/src/__tests__/`)

- [ ] `routes/config.test.ts`: POST /api/config/scenario with "wind" returns 200 and updated scenario
- [ ] `routes/config.test.ts`: POST /api/config/scenario with "battery" returns 200
- [ ] `routes/config.test.ts`: POST /api/config/scenario with "mixed" returns 200
- [ ] `routes/config.test.ts`: POST /api/config/scenario with "invalid_name" returns 400 with error message
- [ ] `routes/admin.test.ts`: POST /api/admin/reset without X-API-Key returns 401
- [ ] `routes/admin.test.ts`: POST /api/admin/reset with wrong X-API-Key returns 401
- [ ] `routes/admin.test.ts`: POST /api/admin/reset with correct X-API-Key returns 200

### Frontend tests (`frontend/src/__tests__/`)

- [ ] `components/ScenarioSwitcher.test.tsx`: Renders 3 scenario options (Wind Farm, Battery Site, Mixed Fleet)
- [ ] `components/ScenarioSwitcher.test.tsx`: Active scenario is visually highlighted
- [ ] `components/ScenarioSwitcher.test.tsx`: Clicking a scenario calls POST /api/config/scenario
- [ ] `components/ResetDialog.test.tsx`: Reset button opens confirmation dialog
- [ ] `components/ResetDialog.test.tsx`: Confirming reset calls POST /api/admin/reset
- [ ] `components/ResetDialog.test.tsx`: Cancel closes dialog without calling API
- [ ] `components/SkeletonLoader.test.tsx`: Skeleton loader renders placeholder animation
- [ ] `components/Toast.test.tsx`: Toast displays error message and auto-dismisses
- [ ] `components/ConnectionBanner.test.tsx`: Banner renders "Connection Lost" text when connection is down
- [ ] `components/ConnectionBanner.test.tsx`: Banner is hidden when connection is healthy
- [ ] `layout/Header.test.tsx`: Header displays active scenario name

### Integration tests

- [ ] `formatting.test.ts`: Number formatter outputs locale-appropriate commas and 2 decimal places (e.g., 1234567.89 -> "1,234,567.89")
- [ ] `formatting.test.ts`: Timestamp formatter outputs human-readable ISO format

### Start script tests

- [ ] `start-script.test.ts`: Root package.json contains `demo:start` script
- [ ] `start-script.test.ts`: Root package.json lists `concurrently` (or equivalent) as devDependency
- [ ] `readme.test.ts`: Root README.md contains sections: Prerequisites, Setup, Environment Variables, Architecture, SDT Compression, Troubleshooting

## Gates

Run `bash gates.sh` to verify. Same 13 gates as all phases.

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
3. All 22 tests from the test plan above exist as real test files and are passing
4. Scenario switcher works with 3 scenarios and validates input
5. Reset endpoint is protected by API key authentication
6. All pages have skeleton loaders and error toasts
7. `npm run demo:start` script exists in root package.json
8. README.md has all required sections
9. All Phase 1, 2, 3, and 4 tests still pass

**You MUST verify completion mechanically.** Do NOT self-assess. Run `bash gates.sh` and read the output.

## Instructions

Follow TDD (red-green-refactor):

1. Read context files, especially `progress.txt`
2. **Red**: Write backend scenario and admin route tests
3. **Green**: Implement scenario switching, reset endpoint with API key auth
4. **Red**: Write frontend component tests (ScenarioSwitcher, ResetDialog, SkeletonLoader, Toast, ConnectionBanner)
5. **Green**: Implement the components
6. Add loading states (skeleton loaders) to all data-fetching components
7. Add error handling (toast notifications, connection banner)
8. Create root package.json with `demo:start` script using concurrently
9. Update README.md with all required sections
10. Write formatting and start script tests
11. Do a visual review pass - ensure dark theme, colors, number formatting are consistent
12. Run `bash gates.sh` - all 13 gates should pass
13. Commit and update `progress.txt`

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
