# PRD: Remove AGL Branding — Generic Databricks + Ignition Theme

**Version**: 1.0 | **Status**: Draft | **Date**: 2026-03-13

## Summary

Remove all AGL Energy-specific branding from the Zerobus demo app and replace it with generic Databricks + Inductive Automation (Ignition) theming. The demo keeps its energy/industrial scenario content (wind, BESS, grid) but uses fictional site names and generic terminology. All backend resource names, config defaults, and DAB resource names are also renamed. Success: zero occurrences of "AGL" in the codebase (excluding git history).

## Background

The demo app was originally built for a specific AGL Energy customer engagement. It contains AGL logos, Australian site names (Tomago, Liddell, Broken Hill, Callide, Gladstone), AGL brand colors (#0066B3), NEM-specific market terminology, and AUD currency references. As this is a **public repository** used for general Databricks + Ignition partner demos, the branding needs to be industry-generic.

## Goals

- Remove all AGL Energy branding (logos, colours, text, resource names)
- Replace with Inductive Automation (Ignition) logo as primary partner brand alongside Databricks
- Use fictional, generic industrial site names (not tied to any real company or geography)
- Rename all DAB resources, config defaults, and project metadata from `agl-*` to `zerobus-*` or `ot-*`
- Existing tests continue to pass after renaming

## Non-Goals

- **No new features** — This is a rebrand, not a feature addition
- **No layout or UX changes** — Keep the same page structure, navigation, and component hierarchy
- **No simulator logic changes** — Tag generation profiles keep the same tag structure, just rename providers
- **No SQL schema changes** — The UC catalog/schema/table names are configurable; we change defaults only
- **No analytics model changes** — Revenue-at-risk and health score logic stays the same, just genericize currency/market labels
- **No Makefile variable renames** — Makefile variable overrides (`.env`) are user-facing config, not branding. Only change defaults.
- **No changes to `examples/agl_fleet/`** — The simulator CLI package is a separate scope

## Requirements

### Functional

- FR-1: Replace AGL Energy logo with Inductive Automation (Ignition) logo in Sidebar and Landing page
- FR-2: Replace all AGL brand colour references (`agl-blue`, `#0066B3`, `text-agl-blue`) with an Ignition-appropriate colour
- FR-3: Replace Australian site names with fictional generic names (e.g. "Windpark North", "Battery Hub East", "Solar Ridge")
- FR-4: Replace "AGL OT Lakehouse" title/heading with "OT Lakehouse Demo" or "Ignition OT Lakehouse"
- FR-5: Replace NEM-specific references ("NEM window", "NEM sites", "NEM dispatch prices") with generic market terms ("energy market", "price window", "dispatch prices")
- FR-6: Replace AUD currency references with generic "$" or "USD"
- FR-7: Replace scenario labels "Wind Farm (Hexham)", "Battery Site (Liddell)" with generic names
- FR-8: Replace tag provider prefixes in UI text (`agl_bess`, `agl_grid`, `agl_market`, `agl_cmms`) with generic names (`bess`, `grid`, `market`, `cmms`)
- FR-9: Rename DAB bundle from `zerobus-ignition-agl` to `zerobus-ignition-demo`
- FR-10: Rename DAB app from `zerobus-ignition-agl` to `zerobus-ignition-demo`
- FR-11: Rename DAB variable defaults: catalog `agl_demo` → `ot_demo`, pipeline `agl-etl` → `ot-etl`, job `agl-train-health-model` → `ot-train-health-model`, lakebase instance `agl-demo-lakebase` → `ot-demo-lakebase`
- FR-12: Rename `app.yaml` env defaults: `APP_TARGET_CATALOG` from `agl_demo` to `ot_demo`
- FR-13: Rename `pyproject.toml` project name from `zerobus-ignition-agl-app` to `zerobus-ignition-demo-app`
- FR-14: Rename FastAPI app title from "AGL OT Lakehouse Demo" to "OT Lakehouse Demo"
- FR-15: Update backend config defaults (`config.py`, `query.py`) from `agl_demo` to `ot_demo`
- FR-16: Update backend test fixtures (`conftest.py`, marker text) from `agl_demo` to `ot_demo`
- FR-17: Update simulator profile descriptions to remove "AGL Hexham/Pottinger" and "AGL Liddell/Tomago" references
- FR-18: Update DataGeneration page to use generic site names and provider prefixes
- FR-19: Update all frontend test files that reference AGL-specific tag paths or names
- FR-20: Remove `demo/app/frontend/src/agl/` directory (AGL logo files and branding README)
- FR-21: Remove `demo/app/frontend/BRANDING_LOGOS_ADDENDUM.md` (AGL-specific branding guide)
- FR-22: Update Makefile defaults: `CATALOG`, `SP_PROFILE_NAME`, `PIPELINE_NAME`, `JOB_NAME`, `LAKEBASE_INSTANCE_NAME`
- FR-23: Update `databricks.yml` comments and descriptions to remove "AGL" references

### Non-functional

- NFR-1: All existing vitest tests pass after changes (0 regressions)
- NFR-2: All existing pytest tests pass after changes (0 regressions)
- NFR-3: No broken image references — Inductive Automation logo file must exist at the expected import path

## Design

### Architecture

Pure text/asset replacement — no structural changes. The change touches three layers:

1. **Frontend (React/TSX)**: Logo imports, text strings, colour tokens, test fixtures
2. **Backend (Python/FastAPI)**: Config defaults, log messages, test markers
3. **Infrastructure (YAML)**: DAB bundle config, app.yaml, Makefile defaults

### Key files to modify

**Frontend — UI components:**
- `demo/app/frontend/src/components/Sidebar.tsx` — Logo import, heading text, colour class
- `demo/app/frontend/src/pages/Landing.tsx` — Hero logos, site names, data streams, talk track text, footer
- `demo/app/frontend/src/components/Header.tsx` — Scenario labels
- `demo/app/frontend/src/components/ScenarioSwitcher.tsx` — Scenario labels
- `demo/app/frontend/src/pages/DataGeneration.tsx` — Site names, provider prefixes, profile descriptions
- `demo/app/frontend/src/pages/Analytics.tsx` — NEM references, AUD formatting, en-AU locale
- `demo/app/frontend/src/pages/AssetDetail.tsx` — Tag path references (if AGL-prefixed)

**Frontend — Config/assets:**
- `demo/app/frontend/tailwind.config.ts` — Remove `agl.blue`, add `ignition` colour
- `demo/app/frontend/src/agl/` — DELETE entire directory
- `demo/app/frontend/BRANDING_LOGOS_ADDENDUM.md` — DELETE
- New file: `demo/app/frontend/src/default/ignition-logo.png` — Inductive Automation logo

**Frontend — Tests:**
- `demo/app/frontend/src/__tests__/pages/AssetHierarchy.test.tsx` — AGL tag paths
- `demo/app/frontend/src/__tests__/components/TagTreeView.test.tsx` — AGL tag paths

**Backend:**
- `demo/app/backend/main.py` — FastAPI title, startup log
- `demo/app/backend/config.py` — Default catalog
- `demo/app/backend/services/query.py` — Default catalog, comment about provider prefix
- `demo/app/backend/tests/conftest.py` — Default catalog, marker text
- `demo/app/backend/tests/test_compression_integration.py` — Comment referencing `agl_demo`

**Infrastructure:**
- `databricks.yml` — Bundle name, comments, variable defaults, app resource key, pipeline dependency path
- `demo/app/app.yaml` — Catalog default
- `demo/app/pyproject.toml` — Project name, description, marker text
- `demo/app/README.md` — Title
- `Makefile` — Variable defaults (CATALOG, SP_PROFILE_NAME, PIPELINE_NAME, etc.)

**Simulator profiles:**
- `demo/simulator/src/profiles/wind-turbine.json` — Description field
- `demo/simulator/src/profiles/battery-bess.json` — Description field

### Colour replacement

Replace `agl.blue: '#0066B3'` in Tailwind config with `ignition.blue: '#259BD7'` (Inductive Automation's brand blue from their logo). All `text-agl-blue` classes become `text-ignition-blue`.

### Site name mapping

| Current (AGL) | New (Generic) |
|---|---|
| Tomago, NSW, 100 MW | Windpark North, Region A, 100 MW |
| Liddell, NSW, 150 MW | Battery Hub East, Region B, 150 MW |
| Broken Hill, NSW, 50 MW | Solar Ridge, Region C, 50 MW |
| Callide, QLD, 200 MW | Thermal Plant South, Region D, 200 MW |
| Gladstone, QLD, 175 MW | Grid Station West, Region E, 175 MW |

### Scenario label mapping

| Current | New |
|---|---|
| Wind Farm (Hexham) | Wind Farm |
| Battery Site (Liddell) | Battery Site |
| Mixed Fleet | Mixed Fleet (unchanged) |

### Resource naming mapping

| Current | New |
|---|---|
| `zerobus-ignition-agl` (bundle + app) | `zerobus-ignition-demo` |
| `agl_demo` (catalog) | `ot_demo` |
| `[production] agl-etl` | `[production] ot-etl` |
| `[production] agl-train-health-model` | `[production] ot-train-health-model` |
| `agl-demo-lakebase` | `ot-demo-lakebase` |
| `agl-demo` (SP profile) | `ot-demo` |
| `agl_analytics-0.1.0` (wheel) | `ot_analytics-0.1.0` |
| `zerobus-ignition-agl-app` (pyproject) | `zerobus-ignition-demo-app` |

## Acceptance Criteria

| ID | AC Description (Given/When/Then) | Verifiable | Test Type |
|---|---|---|---|
| AC-1 | Given the full codebase (excluding `.git/`, `node_modules/`), when searching for the string "AGL" (case-sensitive), then zero matches are found in any `.tsx`, `.ts`, `.py`, `.yaml`, `.yml`, `.toml`, `.json`, or `.md` file under `demo/`, `databricks.yml`, or `Makefile` | Machine | pytest |
| AC-2 | Given the full codebase, when searching for `agl_` or `agl-` (case-insensitive), then zero matches are found in any source file under `demo/`, `databricks.yml`, or `Makefile` | Machine | pytest |
| AC-3 | Given the Sidebar component renders, when the sidebar is displayed, then it shows an Inductive Automation logo (not AGL) and the heading "OT Lakehouse" (not "AGL OT Lakehouse") | Machine | vitest |
| AC-4 | Given the Landing page renders, when the hero section is displayed, then it shows the Inductive Automation logo and Databricks logo, and does not contain any text matching "AGL" | Machine | vitest |
| AC-5 | Given the Landing page renders, when the sites section is displayed, then no site name matches "Tomago", "Liddell", "Broken Hill", "Callide", or "Gladstone" | Machine | vitest |
| AC-6 | Given the ScenarioSwitcher renders, when scenario buttons are displayed, then labels do not contain "Hexham" or "Liddell" | Machine | vitest |
| AC-7 | Given the Tailwind config, when colour tokens are inspected, then `agl` colour key does not exist and `ignition` colour key is defined | Machine | vitest |
| AC-8 | Given the FastAPI app, when the app title is read, then it equals "OT Lakehouse Demo" (not "AGL OT Lakehouse Demo") | Machine | pytest |
| AC-9 | Given `databricks.yml`, when parsed, then `bundle.name` equals `zerobus-ignition-demo` and no variable default contains "agl" | Machine | pytest |
| AC-10 | Given the `demo/app/frontend/src/agl/` directory, then it does not exist | Machine | pytest |
| AC-11 | Given the file `demo/app/frontend/src/default/ignition-logo.png`, then it exists and is a valid PNG file | Machine | pytest |
| AC-12 | Given the existing vitest test suite, when `npx vitest run` is executed, then all tests pass with exit code 0 | Machine | vitest |
| AC-13 | Given the existing pytest test suite (unit tests only), when `uv run pytest -m "not integration"` is executed, then all tests pass with exit code 0 | Machine | pytest |
| AC-14 | Given the Analytics page, when revenue summary text is rendered, then currency is displayed as "$" (not "AUD") and no text matches "NEM" | Machine | vitest |
| AC-15 | Given the DataGeneration page renders, when provider names are displayed, then no provider name contains "agl_" prefix | Machine | vitest |
| AC-16 | Given the app sidebar renders, when visually inspected, the Ignition logo is visible and appropriately sized | Manual | manual |

### Verification Plan

| AC | Verification Method | Pass Condition |
|---|---|---|
| AC-1 | `uv run pytest demo/app/backend/tests/gates/test_rebrand_ac1.py -x` | Exit 0 |
| AC-2 | `uv run pytest demo/app/backend/tests/gates/test_rebrand_ac2.py -x` | Exit 0 |
| AC-3 | `npx vitest run demo/app/frontend/src/__tests__/gates/rebrand-ac3.test.tsx` | All assertions pass |
| AC-4 | `npx vitest run demo/app/frontend/src/__tests__/gates/rebrand-ac4.test.tsx` | All assertions pass |
| AC-5 | `npx vitest run demo/app/frontend/src/__tests__/gates/rebrand-ac5.test.tsx` | All assertions pass |
| AC-6 | `npx vitest run demo/app/frontend/src/__tests__/gates/rebrand-ac6.test.tsx` | All assertions pass |
| AC-7 | `npx vitest run demo/app/frontend/src/__tests__/gates/rebrand-ac7.test.ts` | All assertions pass |
| AC-8 | `uv run pytest demo/app/backend/tests/gates/test_rebrand_ac8.py -x` | Exit 0 |
| AC-9 | `uv run pytest demo/app/backend/tests/gates/test_rebrand_ac9.py -x` | Exit 0 |
| AC-10 | `uv run pytest demo/app/backend/tests/gates/test_rebrand_ac10.py -x` | Exit 0 |
| AC-11 | `uv run pytest demo/app/backend/tests/gates/test_rebrand_ac11.py -x` | Exit 0 |
| AC-12 | `cd demo/app/frontend && npx vitest run` | Exit 0 |
| AC-13 | `cd demo/app && uv run pytest -m "not integration" -x` | Exit 0 |
| AC-14 | `npx vitest run demo/app/frontend/src/__tests__/gates/rebrand-ac14.test.tsx` | All assertions pass |
| AC-15 | `npx vitest run demo/app/frontend/src/__tests__/gates/rebrand-ac15.test.tsx` | All assertions pass |
| AC-16 | Manual: Open app, verify Ignition logo renders in sidebar | Reviewer confirms |

## Risks

- **Deployed resources**: Renaming DAB resources (app, pipeline, lakebase) means re-deployment is required. The old `zerobus-ignition-agl` app will need to be deleted before deploying `zerobus-ignition-demo`. Mitigation: Document the migration sequence in the PR description.
- **Inductive Automation logo licensing**: Using the Ignition logo requires permission from Inductive Automation. Mitigation: Use their official partner/press logo if available; flag for manual review (AC-16).
- **Wheel rename**: Renaming `agl_analytics` wheel to `ot_analytics` requires rebuilding and re-uploading. The pipeline DAB config references the wheel path. Mitigation: Include in FR-11 scope.
- **Existing `.env` files**: Users with existing `.env` files containing `agl_demo` will need to update them. Mitigation: Update `.env.example` and document in PR.

## Open Questions

- [ ] Confirm Inductive Automation brand colour — `#259BD7` is estimated from their logo; verify exact hex
- [ ] Confirm we have permission to use the Inductive Automation logo in this public repo
- [ ] Should `examples/agl_fleet/` also be renamed in a follow-up PR?

---

## Agent Handoff

> Machine-readable block consumed by the relentless agent pipeline.
> `relentless-gates` parses `acceptance_criteria[]` to generate failing test stubs.
> `relentless-implement` uses `verify.gates` as its termination gate.
> `relentless-validate` reads `validation_surfaces` for live execution checks.
> `relentless-orchestrate` reads `agent_roles`, `handoff_sequence`, and `completion_criteria` to drive the full loop.

```json
{
  "prd_version": "1.0",
  "feature": "Remove AGL Branding",
  "goal": "Zero occurrences of 'AGL' in demo app, DAB config, and Makefile; Inductive Automation logo replaces AGL logo; all existing tests pass",
  "stack": "fullstack",
  "test_runner": {
    "backend": "cd demo/app && uv run pytest",
    "frontend": "cd demo/app/frontend && npx vitest run"
  },
  "gate_dirs": {
    "backend": "demo/app/backend/tests/gates/",
    "frontend": "demo/app/frontend/src/__tests__/gates/"
  },
  "acceptance_criteria": [
    {
      "id": "AC-1",
      "description": "Given the full codebase (excluding .git/, node_modules/), when searching for 'AGL' (case-sensitive), then zero matches in .tsx/.ts/.py/.yaml/.yml/.toml/.json/.md files under demo/, databricks.yml, or Makefile",
      "verifiable": true,
      "test_type": "pytest",
      "gate_file": "demo/app/backend/tests/gates/test_rebrand_ac1.py",
      "gate_test": "test_ac1_no_agl_uppercase_in_source_files"
    },
    {
      "id": "AC-2",
      "description": "Given the full codebase, when searching for 'agl_' or 'agl-' (case-insensitive), then zero matches in source files under demo/, databricks.yml, or Makefile",
      "verifiable": true,
      "test_type": "pytest",
      "gate_file": "demo/app/backend/tests/gates/test_rebrand_ac2.py",
      "gate_test": "test_ac2_no_agl_prefixed_identifiers"
    },
    {
      "id": "AC-3",
      "description": "Given the Sidebar component renders, when displayed, then it shows an Inductive Automation logo and the heading 'OT Lakehouse' (not 'AGL OT Lakehouse')",
      "verifiable": true,
      "test_type": "vitest",
      "gate_file": "demo/app/frontend/src/__tests__/gates/rebrand-ac3.test.tsx",
      "gate_test": "AC-3: Sidebar shows Ignition logo and generic heading"
    },
    {
      "id": "AC-4",
      "description": "Given the Landing page renders, when the hero section is displayed, then it shows the Inductive Automation logo and does not contain 'AGL'",
      "verifiable": true,
      "test_type": "vitest",
      "gate_file": "demo/app/frontend/src/__tests__/gates/rebrand-ac4.test.tsx",
      "gate_test": "AC-4: Landing page hero has no AGL references"
    },
    {
      "id": "AC-5",
      "description": "Given the Landing page renders, when sites section displayed, then no site name matches Tomago, Liddell, Broken Hill, Callide, or Gladstone",
      "verifiable": true,
      "test_type": "vitest",
      "gate_file": "demo/app/frontend/src/__tests__/gates/rebrand-ac5.test.tsx",
      "gate_test": "AC-5: Landing page uses generic site names"
    },
    {
      "id": "AC-6",
      "description": "Given the ScenarioSwitcher renders, when scenario buttons displayed, then labels do not contain Hexham or Liddell",
      "verifiable": true,
      "test_type": "vitest",
      "gate_file": "demo/app/frontend/src/__tests__/gates/rebrand-ac6.test.tsx",
      "gate_test": "AC-6: Scenario labels are generic"
    },
    {
      "id": "AC-7",
      "description": "Given the Tailwind config, when colour tokens inspected, then 'agl' key does not exist and 'ignition' key is defined",
      "verifiable": true,
      "test_type": "vitest",
      "gate_file": "demo/app/frontend/src/__tests__/gates/rebrand-ac7.test.ts",
      "gate_test": "AC-7: Tailwind config uses ignition colour not agl"
    },
    {
      "id": "AC-8",
      "description": "Given the FastAPI app, when app title is read, then it equals 'OT Lakehouse Demo'",
      "verifiable": true,
      "test_type": "pytest",
      "gate_file": "demo/app/backend/tests/gates/test_rebrand_ac8.py",
      "gate_test": "test_ac8_fastapi_title_is_generic"
    },
    {
      "id": "AC-9",
      "description": "Given databricks.yml, when parsed, then bundle.name equals 'zerobus-ignition-demo' and no variable default contains 'agl'",
      "verifiable": true,
      "test_type": "pytest",
      "gate_file": "demo/app/backend/tests/gates/test_rebrand_ac9.py",
      "gate_test": "test_ac9_databricks_yml_no_agl"
    },
    {
      "id": "AC-10",
      "description": "Given the demo/app/frontend/src/agl/ directory, then it does not exist",
      "verifiable": true,
      "test_type": "pytest",
      "gate_file": "demo/app/backend/tests/gates/test_rebrand_ac10.py",
      "gate_test": "test_ac10_agl_directory_removed"
    },
    {
      "id": "AC-11",
      "description": "Given the file demo/app/frontend/src/default/ignition-logo.png, then it exists and is a valid PNG",
      "verifiable": true,
      "test_type": "pytest",
      "gate_file": "demo/app/backend/tests/gates/test_rebrand_ac11.py",
      "gate_test": "test_ac11_ignition_logo_exists"
    },
    {
      "id": "AC-12",
      "description": "Given the existing vitest test suite, when npx vitest run is executed, then all tests pass with exit 0",
      "verifiable": true,
      "test_type": "vitest",
      "gate_file": "demo/app/frontend/src/__tests__/gates/rebrand-ac12.test.ts",
      "gate_test": "AC-12: Full vitest suite passes (meta-gate — run entire suite)"
    },
    {
      "id": "AC-13",
      "description": "Given the existing pytest test suite (unit tests only), when uv run pytest -m 'not integration' is executed, then all tests pass with exit 0",
      "verifiable": true,
      "test_type": "pytest",
      "gate_file": "demo/app/backend/tests/gates/test_rebrand_ac13.py",
      "gate_test": "test_ac13_existing_pytest_suite_passes"
    },
    {
      "id": "AC-14",
      "description": "Given the Analytics page renders, when revenue summary is displayed, then currency shows '$' not 'AUD' and no text matches 'NEM'",
      "verifiable": true,
      "test_type": "vitest",
      "gate_file": "demo/app/frontend/src/__tests__/gates/rebrand-ac14.test.tsx",
      "gate_test": "AC-14: Analytics page uses generic currency and market terms"
    },
    {
      "id": "AC-15",
      "description": "Given the DataGeneration page renders, when provider names displayed, then no provider name contains 'agl_' prefix",
      "verifiable": true,
      "test_type": "vitest",
      "gate_file": "demo/app/frontend/src/__tests__/gates/rebrand-ac15.test.tsx",
      "gate_test": "AC-15: DataGeneration page uses generic provider names"
    },
    {
      "id": "AC-16",
      "description": "Given the app sidebar renders, when visually inspected, the Ignition logo is visible and appropriately sized",
      "verifiable": false,
      "test_type": "manual",
      "skip_reason": "requires browser/human judgment for visual logo quality"
    }
  ],
  "must_have": [
    "Replace AGL logo with Inductive Automation logo",
    "Replace all AGL text references with generic terms",
    "Replace Australian site names with fictional names",
    "Rename DAB resources from agl-* to ot-*/zerobus-*",
    "All existing tests pass"
  ],
  "out_of_scope": [
    "New features or layout changes",
    "Simulator logic changes",
    "SQL schema changes",
    "examples/agl_fleet/ renaming",
    "Analytics model changes"
  ],
  "constraints": {
    "tech_stack": "React 18 + TypeScript + Vite + Tailwind (frontend), Python + FastAPI (backend), YAML (DAB config)",
    "key_files": [
      "demo/app/frontend/src/components/Sidebar.tsx",
      "demo/app/frontend/src/pages/Landing.tsx",
      "demo/app/frontend/src/pages/DataGeneration.tsx",
      "demo/app/frontend/src/pages/Analytics.tsx",
      "demo/app/frontend/src/components/Header.tsx",
      "demo/app/frontend/src/components/ScenarioSwitcher.tsx",
      "demo/app/frontend/tailwind.config.ts",
      "demo/app/backend/main.py",
      "demo/app/backend/config.py",
      "demo/app/backend/services/query.py",
      "demo/app/backend/tests/conftest.py",
      "databricks.yml",
      "demo/app/app.yaml",
      "demo/app/pyproject.toml",
      "Makefile",
      "demo/simulator/src/profiles/wind-turbine.json",
      "demo/simulator/src/profiles/battery-bess.json"
    ],
    "patterns": "Use existing Tailwind design tokens, follow current file structure, keep component APIs unchanged"
  },
  "escalate_on": [
    "Cannot find or create an Inductive Automation logo PNG — ask user to provide one",
    "Test references AGL-specific data from a live Databricks query (integration test) — skip, don't modify query logic",
    "Wheel package name agl_analytics referenced in pipeline SQL — flag for separate PR",
    "Ambiguity about whether a reference is AGL-specific or generic industrial terminology"
  ],
  "verify": {
    "gates": "cd demo/app && uv run pytest backend/tests/gates/ -x && cd frontend && npx vitest run src/__tests__/gates/",
    "smoke_test": "cd demo/app/frontend && npx vitest run --reporter=verbose 2>&1 | tail -5",
    "full_suite": "cd demo/app && uv run pytest -m 'not integration' -x && cd frontend && npx vitest run",
    "requires_running_app": false
  },
  "validation_surfaces": {
    "frontend": {
      "type": "browser",
      "base_url": "http://localhost:5173",
      "routes": [
        {"path": "/", "expect": "no AGL text, Ignition logo visible, generic site names"},
        {"path": "/dashboard", "expect": "no AGL references in header or scenario switcher"},
        {"path": "/analytics", "expect": "no NEM or AUD references"},
        {"path": "/data-generation", "expect": "no agl_ provider prefixes"}
      ]
    }
  },
  "log_commands": {
    "bundle_validate": "databricks bundle validate --profile daveok"
  },
  "agent_roles": {
    "implementer": "write code, pass TDD gates",
    "validator": "run live execution, capture errors via Chrome DevTools",
    "remediator": "receive structured error report, patch and re-validate",
    "orchestrator": "relentless-orchestrate — loop until completion_criteria met"
  },
  "handoff_sequence": ["gates", "implementer", "validator", "remediator", "validator"],
  "escalate_to_human_on": [
    "permission_denied",
    "missing_logo_asset",
    "integration_test_failures",
    "loop_count > 5"
  ],
  "completion_criteria": {
    "tdd_gates": "all machine gates exit 0",
    "live_execution": "zero console errors, zero failed network requests on /, /dashboard, /analytics, /data-generation",
    "regression": "full test suite unchanged",
    "manual_acs": "AC-16 flagged for human review"
  }
}
```
