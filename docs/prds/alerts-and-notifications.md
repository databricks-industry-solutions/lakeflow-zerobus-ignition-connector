# PRD: Alerts & Notifications
**Author:** david.okeeffe | **Date:** 2026-03-24 | **Status:** DRAFT

## Problem Statement

The OT Lakehouse demo app computes per-asset health scores (0.0-1.0) and revenue-at-risk calculations via Lakeflow pipeline materialized views (`health_scores`, `revenue_risk`). Recommended actions are hardcoded inline (Critical / Urgent / Schedule / Monitor based on health thresholds). However, there is:

- **No persistent alert history** -- when an asset crosses a health threshold, no event is recorded. Operators cannot see when a degradation started, how long it lasted, or who acknowledged it.
- **No alert lifecycle** -- alerts have no state machine (Open, Acknowledged, Resolved). There is no audit trail of operator response.
- **No configurable thresholds** -- the hardcoded 0.3/0.5/0.8 breakpoints cannot be tuned per asset or per template.
- **No dedicated alert UI** -- operators must mentally scan the health-scores table to spot problems. There are no summary counts, no filters, and no drill-down.

This matters because the demo narrative is: "Your OT data flows from Ignition into Delta Lake in real time -- now show me what *actions* the platform enables." Alerts are the operational bridge between analytics insight and field action.

## User Personas & Stories

- **P1: OT Operations Engineer** -- monitors fleet health during a shift. Needs to see active alerts at a glance, acknowledge them, and verify they auto-resolve when conditions improve.
  - US-1: As an OT operator, I want to see all active alerts sorted by severity so I can triage the most critical issues first.
  - US-2: As an OT operator, I want to acknowledge an alert so my team knows I am handling it.
  - US-3: As an OT operator, I want alerts to auto-resolve when health recovers above the threshold so I do not have to close stale alerts manually.

- **P2: Reliability Engineer** -- reviews alert history for root-cause analysis.
  - US-4: As a reliability engineer, I want to filter alerts by asset, severity, and time range to investigate recurring patterns.
  - US-5: As a reliability engineer, I want to click an alert and see which tags triggered it and the health-score history for that asset.

- **P3: Demo Presenter (Databricks SE / Partner)** -- walks a customer through the platform.
  - US-6: As a demo presenter, I want summary cards showing active critical/warning/info counts so the value is immediately visible.
  - US-7: As a demo presenter, I want to configure alert thresholds in the UI to demonstrate that Databricks is not just a data lake but an operational platform.
  - US-8: As a demo presenter, I want to show how Databricks SQL Alerts can forward notifications to Slack or email (stretch goal -- pattern/documentation only).

## Functional Requirements

### Pipeline Layer (Lakeflow Declarative Pipelines)

1. **FR-1: `alert_thresholds` managed table** -- A UC managed table seeded with default thresholds. Schema:
   - `threshold_id` STRING NOT NULL (PK, UUID)
   - `asset_id` STRING (nullable -- NULL means global/all assets)
   - `template_id` STRING (nullable -- NULL means all templates)
   - `metric_name` STRING NOT NULL (e.g., `health_score`)
   - `operator` STRING NOT NULL (`lt`, `gt`, `eq`, `lte`, `gte`)
   - `threshold_value` DOUBLE NOT NULL
   - `severity` STRING NOT NULL (`critical`, `warning`, `info`)
   - `enabled` BOOLEAN NOT NULL DEFAULT TRUE
   - `created_at` TIMESTAMP NOT NULL
   - `updated_at` TIMESTAMP NOT NULL

2. **FR-2: Default threshold seeds** -- On table creation, insert three rows:
   - `health_score lt 0.3` = `critical`
   - `health_score lt 0.5` = `warning`
   - `health_score lt 0.8` = `info`
   These are global (asset_id = NULL, template_id = NULL).

3. **FR-3: `alert_events` materialized view** -- A Lakeflow MV that joins `health_scores` with `alert_thresholds` to produce alert rows. Schema:
   - `alert_id` STRING NOT NULL (deterministic hash of `asset_id + severity + threshold_id`)
   - `asset_id` STRING NOT NULL
   - `asset_name` STRING (from `silver_asset_registry`, nullable)
   - `severity` STRING NOT NULL (`critical`, `warning`, `info`)
   - `alert_type` STRING NOT NULL (e.g., `health_threshold_breach`)
   - `message` STRING NOT NULL (human-readable, e.g., "Health score 0.22 is below critical threshold 0.3")
   - `health_score` DOUBLE (the actual health score that triggered the alert)
   - `threshold_value` DOUBLE (the threshold that was breached)
   - `primary_risk_tag` STRING (from `health_scores`)
   - `risk_description` STRING (from `health_scores`)
   - `anomaly_tags` ARRAY<STRING> (from `health_scores`)
   - `triggered_at` TIMESTAMP NOT NULL (from `health_scores.scored_at`)
   - `status` STRING NOT NULL (`open`, `acknowledged`, `resolved`)

   The MV evaluates all enabled thresholds against the current health scores. An asset can produce multiple alert rows (one per breached threshold/severity). The most specific threshold wins: asset-level overrides template-level overrides global.

4. **FR-4: Alert acknowledgement state** -- An `alert_acknowledgements` managed table stores operator actions:
   - `alert_id` STRING NOT NULL (FK to `alert_events.alert_id`)
   - `acknowledged_at` TIMESTAMP NOT NULL
   - `acknowledged_by` STRING NOT NULL
   - `note` STRING (optional operator note)

   The backend writes to this table via SQL INSERT. The `alert_events` MV or the backend query joins with this table to derive `status`:
   - If health has recovered above threshold: `resolved`
   - If row exists in `alert_acknowledgements`: `acknowledged`
   - Otherwise: `open`

5. **FR-5: Alert auto-resolution** -- When the pipeline refreshes and an asset's health score no longer breaches the threshold, the alert is no longer emitted by the MV. The backend query marks previously-seen alerts as `resolved` by comparing current MV output with historical state. For the demo, this is acceptable as eventual consistency (MV refresh interval).

### Backend API (FastAPI)

6. **FR-6: `GET /api/alerts`** -- List alerts with query parameters:
   - `severity` (optional, comma-separated: `critical,warning`)
   - `asset_id` (optional, exact match)
   - `status` (optional: `open`, `acknowledged`, `resolved`)
   - `since` (optional, ISO 8601 timestamp -- alerts triggered after this time)
   - `limit` (optional, default 100, max 500)
   - Returns: `{ data: AlertRow[], meta: { timestamp, query_time_ms } }`

7. **FR-7: `POST /api/alerts/{alert_id}/acknowledge`** -- Mark an alert as acknowledged.
   - Request body: `{ acknowledged_by: string, note?: string }`
   - Writes a row to `alert_acknowledgements` table via SQL INSERT.
   - Returns: `{ data: { alert_id, acknowledged_at, acknowledged_by }, meta: { ... } }`
   - Idempotent: re-acknowledging returns the existing acknowledgement.

8. **FR-8: `GET /api/alerts/summary`** -- Aggregate alert counts.
   - Returns: `{ data: { critical: number, warning: number, info: number, total_active: number, acknowledged: number, resolved_last_24h: number }, meta: { ... } }`

9. **FR-9: `GET /api/alert-thresholds`** -- List all configured thresholds.
   - Returns: `{ data: AlertThreshold[], meta: { ... } }`

10. **FR-10: `POST /api/alert-thresholds`** -- Create or update a threshold.
    - Request body: `{ threshold_id?: string, asset_id?: string, template_id?: string, metric_name: string, operator: string, threshold_value: number, severity: string, enabled?: boolean }`
    - If `threshold_id` is provided and exists, UPDATE. Otherwise, INSERT with generated UUID.
    - Returns: `{ data: AlertThreshold, meta: { ... } }`

11. **FR-11: `DELETE /api/alert-thresholds/{threshold_id}`** -- Delete a threshold.
    - Returns: `{ data: { deleted: string }, meta: { ... } }`

### Frontend (React + Tailwind)

12. **FR-12: `/alerts` page** -- New page accessible from the sidebar under "Demo" section, positioned after "Fleet health & revenue risk". Contains:
    - Summary cards row (BigNumberCard components): Active Critical (red accent), Active Warning (amber accent), Active Info (blue/default accent), Total Acknowledged.
    - Filterable alert table below the cards.

13. **FR-13: Alert table** -- Columns: Severity (color-coded badge), Asset, Message, Health Score, Triggered At, Status (badge), Actions (Acknowledge button if status = open).
    - Filters above the table: severity dropdown, asset dropdown, status dropdown, time range picker.
    - Sorted by: severity DESC (critical first), then triggered_at DESC.
    - Auto-refreshes every 10 seconds using the existing `usePolling` hook.

14. **FR-14: Alert detail slide-out panel** -- Clicking a table row opens a right-side slide-out panel showing:
    - Alert metadata (severity, type, message, triggered_at, status)
    - Health score value and threshold value
    - Primary risk tag and risk description (from `health_scores`)
    - Anomaly tags list
    - Recommended action (from `revenue_risk` if available)
    - Acknowledge button (if not yet acknowledged)
    - Link to Analytics page filtered for that asset

15. **FR-15: Acknowledge action** -- Clicking "Acknowledge" in the table row or detail panel:
    - Calls `POST /api/alerts/{alert_id}/acknowledge` with `acknowledged_by` set to `"demo-operator"` (hardcoded for demo; no auth).
    - Optimistically updates the UI (status badge changes to "acknowledged").
    - Shows a Toast confirmation on success.

16. **FR-16: Cross-link from Analytics page** -- In the "Health by asset" table on the Analytics page, each asset row gets a clickable alert icon/badge if that asset has active alerts. Clicking navigates to `/alerts?asset_id={asset_id}`.

17. **FR-17: Sidebar navigation** -- Add "Alerts" to the `mainLinks` array in `Sidebar.tsx`, positioned after "Fleet health & revenue risk" (index 5). Route: `/alerts`.

### Alert Thresholds Configuration UI

18. **FR-18: Threshold management section** -- On the `/alerts` page, below the alert table, a collapsible "Threshold Configuration" section:
    - Table listing all thresholds: metric, operator, value, severity, scope (global/asset/template), enabled toggle.
    - "Add threshold" button opens a form modal.
    - Edit/Delete buttons per row.
    - Uses `GET /api/alert-thresholds`, `POST /api/alert-thresholds`, `DELETE /api/alert-thresholds/{id}`.

### Webhook/Notification Config (Stretch Goal)

19. **FR-19: Databricks SQL Alert documentation panel** -- A read-only informational card on the `/alerts` page (below thresholds) titled "External Notifications (Slack / Email)". Shows step-by-step instructions for setting up a Databricks SQL Alert on the `alert_events` table/view with a Slack webhook or email destination. Includes a "Copy SQL" button for the alert query. This is documentation only -- no actual webhook integration.

## Non-Functional Requirements

1. **NFR-1: Query performance** -- `GET /api/alerts` and `GET /api/alerts/summary` must return within 5 seconds on a running SQL warehouse (consistent with existing analytics query SLAs in the app).

2. **NFR-2: Polling efficiency** -- The frontend polls at 10-second intervals (matching existing pages). The `usePolling` hook's inflight guard prevents request pile-up on slow warehouses.

3. **NFR-3: Consistent UI design** -- All new components use existing Tailwind classes (`bg-surface-card`, `border-gray-200`, `rounded-card`, `shadow-card`, `font-heading`, `text-databricks-primary`, etc.) and existing component patterns (`BigNumberCard`, `usePolling`, `api.ts fetchJson/postJson`).

4. **NFR-4: No authentication dependency** -- The demo app has no user authentication. `acknowledged_by` is a free-text string (default `"demo-operator"`). This is acceptable for the demo scope.

5. **NFR-5: Idempotent writes** -- `POST /api/alerts/{id}/acknowledge` is idempotent. Re-acknowledging the same alert returns success with the existing acknowledgement timestamp.

6. **NFR-6: Schema backward compatibility** -- New tables (`alert_thresholds`, `alert_acknowledgements`) and the new MV (`alert_events`) are additive. Existing tables and MVs are not modified. The pipeline can be deployed incrementally.

7. **NFR-7: Accessibility** -- Severity badges use both color and text labels (not color alone). Interactive elements are keyboard-navigable. The slide-out panel can be closed with Escape.

## Acceptance Criteria

### Pipeline

1. **AC-1:** Given the pipeline has been deployed, when I query `SELECT * FROM {catalog}.{schema}.alert_thresholds`, then I get at least 3 rows with the default seeds (`health_score lt 0.3 critical`, `health_score lt 0.5 warning`, `health_score lt 0.8 info`).

2. **AC-2:** Given health_scores MV contains an asset with health_score = 0.22 and default thresholds are enabled, when the `alert_events` MV refreshes, then it contains rows for that asset with severities `critical`, `warning`, and `info` (one per breached threshold).

3. **AC-3:** Given an alert_event row exists with `alert_id = "abc123"`, when I INSERT into `alert_acknowledgements` with that alert_id, then subsequent queries joining both tables return `status = "acknowledged"`.

4. **AC-4:** Given an asset previously had health_score = 0.22 but has recovered to 0.85, when the `alert_events` MV refreshes, then no alert rows are emitted for that asset (auto-resolution).

### Backend API

5. **AC-5:** Given alert_events contains 5 alerts (2 critical, 2 warning, 1 info), when I call `GET /api/alerts`, then the response body matches `{ data: AlertRow[], meta: { timestamp: string, query_time_ms: number } }` with `data.length === 5`, and each AlertRow has keys: `alert_id`, `asset_id`, `severity`, `alert_type`, `message`, `health_score`, `threshold_value`, `triggered_at`, `status`.

6. **AC-6:** Given alert_events contains alerts for assets A and B, when I call `GET /api/alerts?severity=critical&asset_id=A`, then `data` contains only critical alerts for asset A.

7. **AC-7:** Given an open alert with `alert_id = "abc123"`, when I call `POST /api/alerts/abc123/acknowledge` with body `{ "acknowledged_by": "demo-operator" }`, then the response contains `{ data: { alert_id: "abc123", acknowledged_at: <ISO timestamp>, acknowledged_by: "demo-operator" } }` and subsequent `GET /api/alerts` returns that alert with `status = "acknowledged"`.

8. **AC-8:** Given 2 critical, 2 warning, 1 info active alerts and 1 acknowledged alert, when I call `GET /api/alerts/summary`, then the response contains `{ data: { critical: 2, warning: 2, info: 1, total_active: 5, acknowledged: 1, ... } }`.

9. **AC-9:** Given default thresholds exist, when I call `GET /api/alert-thresholds`, then the response contains `{ data: AlertThreshold[] }` with at least 3 entries, each having keys: `threshold_id`, `asset_id`, `metric_name`, `operator`, `threshold_value`, `severity`, `enabled`.

10. **AC-10:** Given I call `POST /api/alert-thresholds` with `{ "metric_name": "health_score", "operator": "lt", "threshold_value": 0.6, "severity": "warning", "asset_id": "bess_tomago_01" }`, then a new threshold row is created and returned with a generated `threshold_id`.

11. **AC-11:** Given a threshold with `threshold_id = "xyz"`, when I call `DELETE /api/alert-thresholds/xyz`, then the threshold is deleted and subsequent `GET /api/alert-thresholds` does not include it.

### Frontend

12. **AC-12:** Given I navigate to `/alerts`, then the page renders 4 BigNumberCard components with labels "Active Critical", "Active Warning", "Active Info", and "Acknowledged".

13. **AC-13:** Given the alerts API returns 5 alerts, when the `/alerts` page loads, then the alert table renders 5 rows with columns: Severity, Asset, Message, Health Score, Triggered At, Status, Actions.

14. **AC-14:** Given I select "critical" in the severity filter dropdown, then only critical-severity rows are displayed in the table.

15. **AC-15:** Given I click a table row, then a slide-out panel appears on the right showing alert detail fields: severity, message, health_score, threshold_value, primary_risk_tag, anomaly_tags, and an Acknowledge button (if status is open).

16. **AC-16:** Given I click the Acknowledge button in the detail panel for an open alert, then a POST request is sent to `/api/alerts/{alert_id}/acknowledge`, the status badge updates to "acknowledged", and a Toast notification appears.

17. **AC-17:** Given I am on the Analytics page and an asset has active alerts, then an alert icon/badge is visible in that asset's row in the "Health by asset" table, and clicking it navigates to `/alerts?asset_id={asset_id}`.

18. **AC-18:** Given I am on the `/alerts` page, then the "Threshold Configuration" section is visible (collapsed by default) and lists at least 3 default thresholds.

19. **AC-19:** Given I am on the `/alerts` page, then the sidebar shows "Alerts" as a navigation link and it has an active state when the route is `/alerts`.

## Out of Scope

- **Real-time push notifications** -- The app uses polling (10s interval), not WebSockets or SSE. Push is out of scope.
- **User authentication / RBAC** -- No login, no role-based access. `acknowledged_by` is a free-text field.
- **Actual Slack/email webhook integration** -- Only documentation showing how to set up Databricks SQL Alerts is in scope (FR-19). No live webhook calls from the app.
- **Alert escalation / on-call routing** -- No PagerDuty, Opsgenie, or escalation chain integration.
- **Alert suppression / maintenance windows** -- No concept of scheduled downtime suppressing alerts.
- **Non-health-score metrics** -- Only `health_score` is supported as a metric for alert thresholds in v1. Future work could add `soc_pct`, `temperature`, etc.
- **Historical alert timeline chart** -- No time-series visualization of alert open/close over time (could be a fast-follow).
- **Mobile / responsive layout** -- The app is desktop-first for demo use. No mobile-specific layouts.

## Dependencies

| Dependency | Type | Notes |
|---|---|---|
| `health_scores` MV | Pipeline | Must exist and be refreshing. Source of health data for alert evaluation. |
| `silver_asset_registry` table | Pipeline | Provides `asset_name` for alert display. |
| `revenue_risk` MV | Pipeline | Provides `recommended_action` for alert detail panel. Optional (graceful fallback). |
| Databricks SQL Warehouse | Infrastructure | Backend queries run against DBSQL. Must be running for API to function. |
| Lakeflow Pipeline | Infrastructure | Must be deployed and running for MVs to refresh (alert evaluation frequency). |
| `databricks-sdk` Python package | Library | Already in use. Used for SQL statement execution and table writes. |
| `react-router-dom` | Library | Already in use. Needed for `/alerts` route and query parameter handling. |
| Existing UI components | Codebase | `BigNumberCard`, `usePolling`, `Toast`, `fetchJson`/`postJson` from `api.ts`. |

## Open Questions

1. **MV refresh frequency** -- Alert freshness depends on Lakeflow pipeline refresh interval. If the pipeline is configured for continuous mode, alerts update with each micro-batch. If triggered/scheduled, alerts could be minutes stale. Should we document the expected refresh cadence for the demo?

2. **Alert deduplication window** -- When the MV refreshes and the same threshold is still breached, should the `alert_id` be stable (same hash) so it appears as one continuous alert, or should each MV refresh produce a new alert row? The current design uses a deterministic hash (`asset_id + severity + threshold_id`) for stability.

3. **Threshold precedence** -- When an asset has both a global threshold and an asset-specific override for the same metric+severity, the design says "most specific wins." Should we suppress the global alert entirely, or show both but tag them differently?

4. **Acknowledged alert re-triggering** -- If an alert is acknowledged, then the asset recovers (alert resolves), then the asset degrades again -- should this be a new alert (new `alert_id`) or re-open the old one? Current design: new alert (new hash includes MV refresh cycle).

## Technical Notes

### Data Model

```
alert_thresholds (UC managed table)
  - Created by: pipelines/sql/setup_tables.sql (new section) or setup script
  - Seeded by: pipelines/sql/setup_tables.sql INSERT statements

alert_acknowledgements (UC managed table)
  - Created by: pipelines/sql/setup_tables.sql (new section)
  - Written by: backend API via SQL INSERT

alert_events (Lakeflow MV)
  - Created by: pipelines/sdp/transformations/alert_events.py (new file)
  - Reads: health_scores MV, alert_thresholds table, silver_asset_registry table
  - Left-joins: alert_acknowledgements for status derivation
```

### Pipeline Module Path

```
pipelines/sdp/transformations/alert_events.py
  - @dp.materialized_view(name="alert_events")
  - Follows pattern of silver_analytics.py and revenue_risk.py
  - Uses agl_analytics.config.table() for fully-qualified references
```

### Backend Module Paths

```
demo/app/backend/routes/alerts.py (new file)
  - router = APIRouter(prefix="/api/alerts")
  - GET  /api/alerts
  - POST /api/alerts/{alert_id}/acknowledge
  - GET  /api/alerts/summary
  - GET  /api/alert-thresholds
  - POST /api/alert-thresholds
  - DELETE /api/alert-thresholds/{threshold_id}
  - Registered in demo/app/backend/main.py: app.include_router(alerts.router)

demo/app/backend/services/query.py (modified)
  - Add query builders: _alert_events(), _alert_summary(), _alert_thresholds(),
    _alert_acknowledge(), _alert_threshold_upsert(), _alert_threshold_delete()
  - Register in _QUERIES dict: "alertEvents", "alertSummary", "alertThresholds", etc.
```

### Frontend Module Paths

```
demo/app/frontend/src/pages/Alerts.tsx (new file)
  - Main alerts page with summary cards, filter bar, alert table, threshold config

demo/app/frontend/src/components/AlertDetailPanel.tsx (new file)
  - Slide-out panel for alert detail view

demo/app/frontend/src/components/ThresholdFormModal.tsx (new file)
  - Modal form for creating/editing thresholds

demo/app/frontend/src/services/api.ts (modified)
  - Add alert-related types: AlertRow, AlertSummary, AlertThreshold
  - Add api.alerts namespace: getAlerts(), acknowledge(), getSummary(),
    getThresholds(), createThreshold(), deleteThreshold()

demo/app/frontend/src/App.tsx (modified)
  - Import Alerts page, add <Route path="/alerts" element={<Alerts />} />

demo/app/frontend/src/components/Sidebar.tsx (modified)
  - Add { to: '/alerts', label: 'Alerts' } to mainLinks after 'Fleet health & revenue risk'

demo/app/frontend/src/pages/Analytics.tsx (modified)
  - Add alert icon/badge per asset row linking to /alerts?asset_id=X
```

### API Response Shapes

```typescript
// AlertRow (from GET /api/alerts)
interface AlertRow {
  alert_id: string;
  asset_id: string;
  asset_name: string | null;
  severity: 'critical' | 'warning' | 'info';
  alert_type: string;
  message: string;
  health_score: number;
  threshold_value: number;
  primary_risk_tag: string | null;
  risk_description: string | null;
  anomaly_tags: string[] | null;
  triggered_at: string;
  status: 'open' | 'acknowledged' | 'resolved';
  acknowledged_at: string | null;
  acknowledged_by: string | null;
}

// AlertSummary (from GET /api/alerts/summary)
interface AlertSummary {
  critical: number;
  warning: number;
  info: number;
  total_active: number;
  acknowledged: number;
  resolved_last_24h: number;
}

// AlertThreshold (from GET /api/alert-thresholds)
interface AlertThreshold {
  threshold_id: string;
  asset_id: string | null;
  template_id: string | null;
  metric_name: string;
  operator: string;
  threshold_value: number;
  severity: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### SQL Table DDL (for `setup_tables.sql`)

```sql
-- Alert thresholds configuration
CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.alert_thresholds (
  threshold_id   STRING      NOT NULL COMMENT 'UUID primary key',
  asset_id       STRING               COMMENT 'Specific asset (NULL = global)',
  template_id    STRING               COMMENT 'Specific template (NULL = all)',
  metric_name    STRING      NOT NULL COMMENT 'Metric to evaluate (e.g. health_score)',
  operator       STRING      NOT NULL COMMENT 'Comparison operator: lt, gt, eq, lte, gte',
  threshold_value DOUBLE     NOT NULL COMMENT 'Threshold value',
  severity       STRING      NOT NULL COMMENT 'critical, warning, info',
  enabled        BOOLEAN     NOT NULL COMMENT 'Whether this threshold is active',
  created_at     TIMESTAMP   NOT NULL COMMENT 'Row creation time',
  updated_at     TIMESTAMP   NOT NULL COMMENT 'Last modification time'
)
COMMENT 'Configurable alert thresholds for health score monitoring';

-- Alert acknowledgements (operator actions)
CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.alert_acknowledgements (
  alert_id         STRING      NOT NULL COMMENT 'References alert_events.alert_id',
  acknowledged_at  TIMESTAMP   NOT NULL COMMENT 'When the alert was acknowledged',
  acknowledged_by  STRING      NOT NULL COMMENT 'Operator identifier',
  note             STRING               COMMENT 'Optional operator note'
)
COMMENT 'Operator acknowledgement records for alerts';

-- Default threshold seeds
INSERT INTO ${catalog}.${schema}.alert_thresholds VALUES
  (uuid(), NULL, NULL, 'health_score', 'lt', 0.3, 'critical', TRUE, current_timestamp(), current_timestamp()),
  (uuid(), NULL, NULL, 'health_score', 'lt', 0.5, 'warning',  TRUE, current_timestamp(), current_timestamp()),
  (uuid(), NULL, NULL, 'health_score', 'lt', 0.8, 'info',     TRUE, current_timestamp(), current_timestamp());
```
