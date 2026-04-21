# PRD: Configurable Thresholds and Custom Alert Rules
**Author:** david.okeeffe | **Date:** 2026-03-24 | **Status:** DRAFT

## Problem Statement

Health score thresholds (0.8 / 0.5 / 0.3), price thresholds (300 AUD/MWh), and market risk levels are hardcoded across multiple pipeline transformations (`revenue_risk.py`, `revenue.py`, `data_blend_summary.sql`). SDT compression profiles (32 rules in `sdt_config`) are stored in Unity Catalog but editable only via a single global slider in the demo app -- they cannot be managed per tag class.

When an OT engineer, reliability engineer, or demo presenter asks "can I change these thresholds?", the answer today is no -- not without editing Python source code and redeploying the SDP pipeline.

This blocks two key demo scenarios:
1. **Threshold tuning** -- showing that Databricks enables data-driven threshold management, not just static alarm limits inherited from the historian.
2. **Per-asset override** -- demonstrating hierarchical configuration (global defaults, template-level, asset-level) that mirrors how OT engineers think about alarm management.

## User Personas & Stories

**Reliability Engineer (RE)** -- manages alarm limits and health thresholds for a fleet of BESS/grid assets.
- As an RE, I want to adjust the health score threshold that triggers "Urgent maintenance" so that I can tune alert sensitivity to my fleet's risk tolerance.
- As an RE, I want to set a different health threshold for a specific BESS unit that has known degradation so that I avoid false alarms on that asset.
- As an RE, I want to see how many assets are currently violating a threshold before I change it so that I can predict the impact of a threshold change.

**OT Engineer** -- manages data compression and tag configuration at the edge.
- As an OT engineer, I want to view all 32 SDT compression rules grouped by tag class so that I can understand the compression strategy.
- As an OT engineer, I want to edit the deviation percentage and heartbeat interval for a specific tag class (e.g., temperature sensors) and push the change to the Ignition gateway so that I can tune compression without SSH access.

**Demo Presenter** -- runs live demos for prospects.
- As a demo presenter, I want to change a price threshold from 300 to 200 AUD/MWh and immediately see more assets flagged as "at risk" so that I can show the system's responsiveness.
- As a demo presenter, I want a "Reset to defaults" button so that I can quickly restore the demo to a known-good state between presentations.

## Functional Requirements

### Threshold Configuration Table (UC)

1. **FR-1**: Create a `threshold_config` table in Unity Catalog (`{catalog}.{schema}.threshold_config`) with columns: `config_id` (STRING, UUID), `scope` (STRING: 'global' | 'template' | 'asset'), `scope_id` (STRING, nullable -- null for global, template_id for template, asset_id for asset), `metric_name` (STRING), `operator` (STRING: 'lt' | 'gt' | 'lte' | 'gte' | 'eq'), `threshold_value` (DOUBLE), `severity` (STRING: 'critical' | 'warning' | 'info'), `action_template` (STRING, nullable -- recommended action text), `enabled` (BOOLEAN), `created_at` (TIMESTAMP), `updated_at` (TIMESTAMP).

2. **FR-2**: Seed the table with the current hardcoded defaults on first deploy:
   - `health_score` > 0.8, severity=info, action="Monitor - no action needed"
   - `health_score` <= 0.8 AND > 0.5, severity=warning, action="Schedule inspection before {window_start}"
   - `health_score` <= 0.5 AND > 0.3, severity=warning, action="Urgent: schedule maintenance tonight"
   - `health_score` <= 0.3, severity=critical, action="Critical: consider preemptive shutdown and repair"
   - `spot_price_aud_mwh` > 300, severity=warning, action="High price window detected"
   - `market_risk_level` composite rule: rrp > 300 AND health < 0.5 = HIGH, rrp > 300 OR health < 0.5 = MEDIUM

3. **FR-3**: Implement hierarchical resolution: when evaluating thresholds for an asset, look up asset-level first, then template-level, then global. First match at the most specific scope wins.

### Pipeline Integration

4. **FR-4**: Modify `revenue_risk.py` to read health band thresholds and price threshold from `threshold_config` table instead of using hardcoded constants `HIGH_PRICE_THRESHOLD_AUD_MWH = 300.0` and the 0.8/0.5/0.3 `health_score` bands.

5. **FR-5**: Modify `recommend_action()` in `pipelines/sdp/src/agl_analytics/revenue.py` to accept threshold bands as parameters (with current values as defaults for backward compatibility), rather than hardcoding 0.8/0.5/0.3.

6. **FR-6**: Modify `data_blend_summary.sql` to read the price threshold (currently hardcoded as 300) and health threshold (currently 0.5) from `threshold_config` via a subquery or CTE.

### Threshold Management API

7. **FR-7**: `GET /api/thresholds` -- return all threshold rules, ordered by scope (global first, then template, then asset), then by metric_name. Support optional query parameter `?metric=health_score` to filter by metric.

8. **FR-8**: `POST /api/thresholds` -- create a new threshold rule. Validate: metric_name is non-empty, operator is one of the allowed values, threshold_value is a finite number, severity is one of the allowed values, scope is valid, scope_id is required when scope is 'template' or 'asset'. Return the created rule with generated `config_id`.

9. **FR-9**: `PUT /api/thresholds/{config_id}` -- update an existing threshold rule. Return 404 if config_id not found. Return the updated rule.

10. **FR-10**: `DELETE /api/thresholds/{config_id}` -- soft-delete (set enabled=false) or hard-delete a threshold rule. Return 404 if not found. Prevent deletion of seed/default global rules (return 409 Conflict with message).

11. **FR-11**: `GET /api/thresholds/violations` -- for each enabled threshold rule, return the count of assets currently violating it. Uses the latest `health_scores` and `nem_market_snapshot` data. Response shape: `[{config_id, metric_name, threshold_value, violation_count, sample_assets: [...]}]`.

### Threshold Management UI

12. **FR-12**: Add a `/settings/thresholds` page accessible from the sidebar under a new "Settings" section.

13. **FR-13**: Display thresholds in a grouped table: "Global" section header, then one section per template (if any), then one section per asset (if any). Each row shows: metric name, operator + value (e.g., "> 0.8"), severity badge (color-coded: red=critical, amber=warning, blue=info), action template text, enabled toggle, edit/delete actions.

14. **FR-14**: Inline edit: clicking a threshold value cell opens an input field. Pressing Enter or clicking away saves via `PUT /api/thresholds/{id}`. Pressing Escape cancels.

15. **FR-15**: "Add threshold" button opens a form/modal with fields: scope (dropdown), scope_id (dropdown populated from assets/templates, shown only when scope is not 'global'), metric_name (dropdown with known metrics + freetext), operator (dropdown), threshold_value (number input), severity (dropdown), action_template (text input, optional).

16. **FR-16**: "Reset to defaults" button triggers a confirmation dialog, then replaces all global thresholds with the seed values from FR-2. Does not affect template-level or asset-level overrides.

17. **FR-17**: Each threshold row shows a "violations" badge (e.g., "3 assets") pulled from `GET /api/thresholds/violations`. Badge is gray when 0, amber when > 0 and severity=warning, red when > 0 and severity=critical.

### Per-Tag SDT Profile UI

18. **FR-18**: Enhance the existing `/compression` page. Below the existing waterfall chart and global SDT tuning panel, add a "SDT Profiles by Tag Class" section.

19. **FR-19**: Display the 32 SDT rules from `sdt_config` in a table grouped by tag class category (BESS/Battery, Thermal, Grid/POI, Market, Power, CMMS/Counters, Catch-all). Each row shows: tag pattern, comp_dev (abs), comp_dev_percent, comp_max_seconds, comp_min_seconds.

20. **FR-20**: Each row is editable: clicking a value opens an inline number input. Changes are saved to `sdt_config` in Unity Catalog via the existing `PUT /api/compression/sdt-config` endpoint (extended to handle per-pattern updates).

21. **FR-21**: Add a "Push to Gateway" button that reads the current `sdt_config` table, maps it to the `sdtOverrides` JSON format expected by `POST /system/zerobus/config`, and pushes the merged config to the Ignition gateway. The gateway URL is read from an environment variable `IGNITION_GATEWAY_URL` (default: `http://localhost:7088`).

22. **FR-22**: After a successful gateway push, show a success toast. If the gateway is unreachable, show an error toast with the HTTP status or connection error message.

### Backend: SDT Gateway Push

23. **FR-23**: Add `POST /api/compression/push-to-gateway` endpoint. Reads `sdt_config` from UC, maps each row to an `SdtOverride` JSON object (`{pattern, compDev, compDevPercent, compMaxSeconds, compMinSeconds}`), GETs the current gateway config from `/system/zerobus/config`, merges the `sdtOverrides` array, and POSTs the updated config back.

24. **FR-24**: Add `GET /api/compression/sdt-profiles` endpoint that returns SDT config rows enriched with a `tag_class` category field derived from the tag pattern (e.g., `*/temperature_c` -> "Thermal", `*/soc_pct` -> "BESS/Battery").

## Non-Functional Requirements

1. **NFR-1 (Performance)**: `GET /api/thresholds` must respond in < 500ms. Threshold count is expected to remain under 200 rows.

2. **NFR-2 (Performance)**: `GET /api/thresholds/violations` may take up to 2s as it queries `health_scores` and market data. The UI should show a loading spinner and not block the threshold table render.

3. **NFR-3 (Pipeline latency)**: Changes to `threshold_config` take effect on the next SDP pipeline refresh (materialized views). There is no requirement for sub-second threshold propagation to the pipeline. The UI should display a note: "Threshold changes take effect on the next pipeline refresh (typically within 5 minutes)."

4. **NFR-4 (Security)**: Threshold CRUD operations use the same Databricks SQL warehouse auth as existing endpoints (service principal or PAT). No additional auth layer required for the demo app.

5. **NFR-5 (Backward compatibility)**: If the `threshold_config` table does not exist or is empty, `revenue_risk.py` and `recommend_action()` must fall back to the current hardcoded defaults. Existing tests must continue to pass without modification.

6. **NFR-6 (Accessibility)**: Severity badges must have sufficient color contrast (WCAG AA). The threshold table must be keyboard-navigable. Inline edit inputs must have appropriate aria-labels.

7. **NFR-7 (Gateway resilience)**: The "Push to Gateway" operation is best-effort. If the gateway is down, the SDT config in UC is still the source of truth. The UI must clearly indicate success or failure.

## Acceptance Criteria

### Threshold Config Table

1. **AC-1**: Given a fresh deployment, when `setup_tables.sql` is executed, then the `threshold_config` table exists with the schema defined in FR-1 and contains exactly 6 seed rows matching the current hardcoded values.

2. **AC-2**: Given threshold rules at global (health_score > 0.8), template (health_score > 0.7 for template "BESS"), and asset (health_score > 0.6 for asset "bess_tomago_01") scopes, when resolving the threshold for asset "bess_tomago_01" which belongs to template "BESS", then the asset-level threshold (0.6) is used.

3. **AC-3**: Given threshold rules at global and template scopes only, when resolving the threshold for an asset that belongs to template "BESS" but has no asset-level override, then the template-level threshold is used.

### Pipeline Integration

4. **AC-4**: Given `threshold_config` contains a global `spot_price_aud_mwh` threshold of 200 (changed from default 300), when the `revenue_risk` materialized view refreshes, then `high_price` windows include intervals where price > 200 (not > 300).

5. **AC-5**: Given `threshold_config` is empty or the table does not exist, when `revenue_risk.py` executes, then it uses the hardcoded defaults (300 AUD/MWh, 0.8/0.5/0.3 health bands) and does not raise an error.

6. **AC-6**: Given `recommend_action(health_score=0.6, window_start="2026-03-24 16:00")` is called with default thresholds, then the return value is `"Schedule inspection before 2026-03-24 16:00"` (unchanged behavior).

### Threshold API

7. **AC-7**: Given the seed data exists, when `GET /api/thresholds` is called, then the response contains all 6 seed rules with correct field values, ordered by scope (global first) then metric_name.

8. **AC-8**: Given a valid threshold payload `{scope: "asset", scope_id: "bess_tomago_01", metric_name: "health_score", operator: "lt", threshold_value: 0.4, severity: "critical", enabled: true}`, when `POST /api/thresholds` is called, then the response status is 201 and the body contains the created rule with a generated `config_id`.

9. **AC-9**: Given a POST payload with `scope: "asset"` but missing `scope_id`, when `POST /api/thresholds` is called, then the response status is 422 with a validation error message.

10. **AC-10**: Given a threshold `config_id` that exists, when `PUT /api/thresholds/{config_id}` is called with `{threshold_value: 0.9}`, then the response contains the updated rule with `threshold_value: 0.9` and `updated_at` is more recent than `created_at`.

11. **AC-11**: Given a `config_id` that does not exist, when `PUT /api/thresholds/{config_id}` is called, then the response status is 404.

12. **AC-12**: Given a seed global threshold, when `DELETE /api/thresholds/{config_id}` is called, then the response status is 409 with message indicating default rules cannot be deleted.

13. **AC-13**: Given 3 assets with health_score < 0.5 and a threshold rule `health_score < 0.5 severity=critical`, when `GET /api/thresholds/violations` is called, then the response includes an entry with `violation_count: 3`.

### Threshold UI

14. **AC-14**: Given the app is loaded, when navigating to `/settings/thresholds`, then a table is rendered with sections "Global", and any template/asset sections, each showing their threshold rows.

15. **AC-15**: Given a threshold row with value 0.8, when the user clicks the value cell, changes it to 0.7, and presses Enter, then `PUT /api/thresholds/{id}` is called with `threshold_value: 0.7` and the cell displays 0.7 after the response.

16. **AC-16**: Given the user clicks "Reset to defaults" and confirms, then all global thresholds are replaced with seed values and the table re-renders with the original values.

17. **AC-17**: Given the violations endpoint returns `{violation_count: 5}` for a critical threshold, then a red badge reading "5 assets" appears next to that threshold row.

### SDT Profiles UI

18. **AC-18**: Given 32 SDT rules in `sdt_config`, when navigating to `/compression`, then a "SDT Profiles by Tag Class" section appears below the existing tuning panel, showing all 32 rules grouped into categories (BESS/Battery, Thermal, Grid/POI, Market, Power, CMMS/Counters, Catch-all).

19. **AC-19**: Given the user edits `comp_dev_percent` for tag pattern `*/temperature_c` from 0.3 to 0.5 and tabs out, then `PUT /api/compression/sdt-config` is called with `{tag_pattern: "*/temperature_c", comp_dev: 0.3, comp_dev_percent: null, comp_max_seconds: 300, comp_min_seconds: 1}` (preserving other fields) and the cell shows 0.5 after success.

20. **AC-20**: Given the user clicks "Push to Gateway" and the gateway is reachable at `IGNITION_GATEWAY_URL`, then `POST /api/compression/push-to-gateway` responds with 200, the Ignition gateway config's `sdtOverrides` array contains entries matching the `sdt_config` table, and a success toast appears.

21. **AC-21**: Given the user clicks "Push to Gateway" and the gateway is unreachable, then an error toast appears with a message like "Gateway unreachable: Connection refused" and no config is changed.

## Out of Scope

- **Real-time alerting / notifications** -- this PRD covers threshold configuration only. Alert delivery (email, Slack, PagerDuty) is a separate feature.
- **Threshold-based automated actions** -- e.g., automatically shutting down an asset when health drops below critical. Thresholds inform recommendations only.
- **Audit trail / change history** -- no requirement to track who changed which threshold and when (beyond `updated_at`). Can be added later.
- **Multi-tenant / RBAC on thresholds** -- all app users can read and write all thresholds. Role-based restrictions are not in scope for the demo app.
- **Threshold evaluation at the edge (Ignition)** -- thresholds are evaluated in the Databricks pipeline, not pushed to the Ignition gateway. SDT config push is the only gateway interaction.
- **Custom metric definitions** -- users pick from known metrics; defining new computed metrics is out of scope.

## Dependencies

| Dependency | Type | Notes |
|---|---|---|
| `{catalog}.{schema}.threshold_config` table | UC table | New; created by `setup_tables.sql` |
| `{catalog}.{schema}.sdt_config` table | UC table | Existing; already has 32 rows |
| `health_scores` materialized view | SDP pipeline | Existing; used by violations endpoint |
| `nem_market_snapshot` materialized view | SDP pipeline | Existing; used by violations endpoint for price thresholds |
| `POST /system/zerobus/config` | Ignition Gateway API | Existing; used for SDT push. Must be reachable from the Databricks App (or demo host). |
| `SdtOverride` Java class | Ignition module | Existing; defines the JSON shape for per-tag SDT rules in gateway config |
| FastAPI backend | Demo app | Existing; new router mounted at `/api/thresholds` |
| React frontend | Demo app | Existing; new page at `/settings/thresholds`, enhanced `/compression` page |

## Open Questions

1. **Threshold config caching in pipeline** -- Should the SDP pipeline cache threshold_config reads, or re-read on every materialized view refresh? The MV refresh interval is typically 5 minutes, so re-reading each time is likely acceptable. Confirm with pipeline performance testing.

2. **Gateway URL discovery** -- The demo app needs the Ignition gateway URL for SDT push. Should this be an env var (`IGNITION_GATEWAY_URL`), or should it be configurable in the app UI? For the demo, an env var is simplest.

3. **Threshold versioning** -- If a threshold changes between two pipeline refreshes, the materialized view will use the new value. Should we snapshot the thresholds used in each computation for reproducibility? Leaning toward no for the demo scope.

4. **Metric name taxonomy** -- What is the canonical set of metric names? Candidates: `health_score`, `spot_price_aud_mwh`, `trip_probability`, `soc_pct`, `temperature_c`, `poi_frequency_hz`. Should the UI enforce a fixed set or allow freetext?

5. **Template-to-asset mapping** -- The `threshold_config` table uses `scope_id` to reference templates and assets. How do we resolve which template an asset belongs to? The `asset_hierarchy` and `asset_templates` tables exist -- confirm the join path.

## Technical Notes

### New files

| Path | Description |
|---|---|
| `pipelines/sql/setup_tables.sql` | Add `threshold_config` CREATE TABLE + MERGE seed (append to existing file) |
| `demo/app/backend/routes/thresholds.py` | FastAPI router: CRUD + violations endpoints |
| `demo/app/frontend/src/pages/ThresholdSettings.tsx` | Threshold management page |
| `demo/app/frontend/src/components/ThresholdTable.tsx` | Grouped, inline-editable threshold table |
| `demo/app/frontend/src/components/ThresholdFormModal.tsx` | Add/edit threshold modal |
| `demo/app/frontend/src/components/SdtProfilesTable.tsx` | Per-tag-class SDT config table for `/compression` |

### Modified files

| Path | Change |
|---|---|
| `pipelines/sdp/transformations/revenue_risk.py` | Read thresholds from `threshold_config`; fall back to constants |
| `pipelines/sdp/src/agl_analytics/revenue.py` | `recommend_action()` accepts threshold bands as parameters |
| `pipelines/sdp/transformations/data_blend_summary.sql` | Replace hardcoded 300 / 0.5 with subquery from `threshold_config` |
| `demo/app/backend/main.py` | Import and mount `thresholds` router |
| `demo/app/backend/services/query.py` | Add query builders for threshold CRUD, violations, and SDT profile enrichment |
| `demo/app/frontend/src/App.tsx` | Add `/settings/thresholds` route |
| `demo/app/frontend/src/components/Sidebar.tsx` | Add "Settings" section with "Thresholds" link |
| `demo/app/frontend/src/pages/Compression.tsx` | Integrate `SdtProfilesTable` and "Push to Gateway" button |
| `demo/app/frontend/src/services/api.ts` | Add threshold API methods and SDT profiles/push methods |
| `demo/app/backend/routes/compression.py` | Add `push-to-gateway` endpoint |
| `demo/app/backend/config.py` | Add `ignition_gateway_url` from env var |

### Data model: threshold_config

```sql
CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.threshold_config (
  config_id       STRING      NOT NULL COMMENT 'UUID primary key',
  scope           STRING      NOT NULL COMMENT 'global | template | asset',
  scope_id        STRING               COMMENT 'NULL for global, template_id or asset_id',
  metric_name     STRING      NOT NULL COMMENT 'e.g. health_score, spot_price_aud_mwh',
  operator        STRING      NOT NULL COMMENT 'lt | gt | lte | gte | eq',
  threshold_value DOUBLE      NOT NULL COMMENT 'Numeric threshold',
  severity        STRING      NOT NULL COMMENT 'critical | warning | info',
  action_template STRING               COMMENT 'Recommended action text (supports {window_start} placeholder)',
  enabled         BOOLEAN     NOT NULL DEFAULT true COMMENT 'Toggle without deleting',
  is_default      BOOLEAN     NOT NULL DEFAULT false COMMENT 'True for seed rows (cannot be deleted)',
  created_at      TIMESTAMP   NOT NULL DEFAULT current_timestamp(),
  updated_at      TIMESTAMP   NOT NULL DEFAULT current_timestamp()
)
COMMENT 'Configurable threshold rules for health, price, and alert severity';
```

### API contracts

**POST /api/thresholds**
```json
{
  "scope": "asset",
  "scope_id": "bess_tomago_01",
  "metric_name": "health_score",
  "operator": "lt",
  "threshold_value": 0.4,
  "severity": "critical",
  "action_template": "Emergency shutdown required",
  "enabled": true
}
```

**GET /api/thresholds/violations**
```json
{
  "data": [
    {
      "config_id": "uuid-1",
      "metric_name": "health_score",
      "operator": "lt",
      "threshold_value": 0.5,
      "severity": "critical",
      "violation_count": 3,
      "sample_assets": ["bess_tomago_01", "bess_tomago_03", "bess_liddell_02"]
    }
  ],
  "meta": { "timestamp": "...", "query_time_ms": 450 }
}
```

**POST /api/compression/push-to-gateway**
```json
// Request: empty body (reads sdt_config from UC)
// Response:
{
  "data": {
    "rules_pushed": 32,
    "gateway_url": "http://localhost:7088",
    "gateway_response_status": 200
  },
  "meta": { "timestamp": "...", "query_time_ms": 320 }
}
```

### SDT tag class mapping (for FR-24)

Used to derive the `tag_class` grouping from tag patterns:

| Pattern prefix/keyword | Tag class |
|---|---|
| `*/soc_pct`, `*/soh_pct`, `*/energy_available*`, `*/bess_*`, `*/dccurrent*`, `*/dcvoltage*`, `*/max_charge*`, `*/max_discharge*` | BESS / Battery |
| `*/temperature*`, `*/ambient_temp*`, `*/max_rack_temp*`, `*/coolant*` | Thermal |
| `*/poi_*`, `*/frequency_hz`, `*/voltage_kv`, `*/dispatch*`, `*/curtailment*` | Grid / POI |
| `*/rrp_*`, `*/fcas_*` | Market |
| `*/power_*`, `*/activepower*`, `*/reactivepower*` | Power |
| `*/alarm*`, `*/work_orders`, `*/*_count` | CMMS / Counters |
| `*` (catch-all) | Default |

### Threshold resolution algorithm (pseudocode)

```python
def resolve_threshold(asset_id: str, template_id: str | None, metric: str, rules: list[ThresholdRule]) -> ThresholdRule | None:
    """Return the most specific enabled threshold for an asset + metric."""
    asset_rules = [r for r in rules if r.scope == 'asset' and r.scope_id == asset_id and r.metric_name == metric and r.enabled]
    if asset_rules:
        return asset_rules[0]

    if template_id:
        template_rules = [r for r in rules if r.scope == 'template' and r.scope_id == template_id and r.metric_name == metric and r.enabled]
        if template_rules:
            return template_rules[0]

    global_rules = [r for r in rules if r.scope == 'global' and r.metric_name == metric and r.enabled]
    if global_rules:
        return global_rules[0]

    return None  # fall back to hardcoded defaults
```

### Expected test module paths

| Test path | Coverage |
|---|---|
| `demo/app/backend/tests/test_thresholds_api.py` | CRUD endpoints, validation, 404/409 error cases |
| `demo/app/backend/tests/test_threshold_violations.py` | Violations query with mocked health/market data |
| `demo/app/backend/tests/test_compression_push.py` | Gateway push logic, error handling for unreachable gateway |
| `demo/app/frontend/src/__tests__/pages/ThresholdSettings.test.tsx` | Page render, inline edit, add/delete, reset |
| `demo/app/frontend/src/__tests__/components/SdtProfilesTable.test.tsx` | Grouped display, inline edit, push button |
| `pipelines/sdp/tests/test_threshold_resolution.py` | Hierarchical resolution logic, fallback to defaults |
| `pipelines/sdp/tests/test_revenue.py` | Extended: `recommend_action` with custom threshold params |
