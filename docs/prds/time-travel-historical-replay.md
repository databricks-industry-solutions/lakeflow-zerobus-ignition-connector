# PRD: Time Travel and Historical Replay

**Author:** david.okeeffe | **Date:** 2026-03-24 | **Status:** COMPLETE

> **Implementation:** Commit f27d1e0
> **Test results:** 23 passing (12 backend + 11 frontend), 0 failing
> All gate tests green.

## Problem Statement

The demo app's Asset Detail page (`/assets/{id}`) currently offers only fixed 5-minute, 15-minute, and 60-minute lookback windows for tag history charts. There is no way to select an arbitrary date-time range, no point-in-time fleet snapshot, no event forensics drill-down, and no data export. This is a critical gap: historian users expect to query "what happened at 14:30 on Tuesday" as basic functionality. Without these capabilities, the demo fails to showcase Delta Lake's time travel -- one of its strongest differentiators over traditional historians and SCADA systems.

**Who it affects:**
- Demo audience (prospective customers evaluating Databricks for OT/IIoT) -- they cannot see the full value of Delta Lake for historical analysis
- Sales engineers running live demos -- they lack a "wow moment" around time travel and forensics
- OT engineers evaluating the connector -- they expect historian-grade temporal queries as table stakes

## User Personas & Stories

- As a **demo attendee**, I want to select an arbitrary date-time range on the asset detail page so that I can explore tag history beyond the last hour.
- As a **reliability engineer**, I want to see the fleet state at a specific point in time so that I can understand what conditions existed before a failure event.
- As an **OT analyst**, I want to compare the fleet state "then vs now" so that I can assess whether corrective actions improved asset health.
- As a **site operator**, I want to drill into raw tag events surrounding an alert so that I can perform root cause analysis.
- As a **data engineer**, I want to export tag data as CSV for a given time range so that I can feed it into offline analysis tools.
- As a **sales engineer**, I want to showcase Delta Lake `TIMESTAMP AS OF` queries in the UI so that I can demonstrate a concrete advantage over traditional historians.

## Functional Requirements

### FR-1: Extended Time Range Selector (Asset Detail Page)

1. **FR-1.1**: Replace the existing fixed 5/15/60 minute button group with: `5m`, `15m`, `1h`, `6h`, `24h`, `7d`, `30d`, `Custom`.
2. **FR-1.2**: When `Custom` is selected, display a date-time range picker with `From` and `To` fields. Each field must include a calendar date picker and a time input (HH:MM). Default `From` to 1 hour ago, `To` to now.
3. **FR-1.3**: The time range selector component must be reusable (shared component) so other pages can adopt it.
4. **FR-1.4**: For ranges > 1 hour, the backend must downsample data using SQL time-bucketed averages:
   - 1h < range <= 6h: 1-minute averages
   - 6h < range <= 24h: 5-minute averages
   - 24h < range <= 7d: 15-minute averages
   - 7d < range <= 30d: 1-hour averages
5. **FR-1.5**: The chart X-axis label format must adapt to range duration (e.g., "HH:MM" for intraday, "MMM DD HH:MM" for multi-day).
6. **FR-1.6**: A loading indicator must display while longer-range queries execute (these may take several seconds on a SQL warehouse).
7. **FR-1.7**: The URL must encode the selected time range as query parameters (`?from=ISO&to=ISO` or `?range=5m`) so that links are shareable and browser back/forward works.

### FR-2: Point-in-Time Fleet Snapshot

1. **FR-2.1**: Add a "Fleet Snapshot" section to the Analytics page (`/analytics`) with a date-time picker labeled "Show fleet state at".
2. **FR-2.2**: On submit, query the `health_scores` Delta table using `TIMESTAMP AS OF` to retrieve health scores, primary risk tags, and anomaly tags as they existed at the selected timestamp.
3. **FR-2.3**: Display results in a sortable table: asset name, site, health score (color-coded), primary risk tag, risk description, estimated hours to failure.
4. **FR-2.4**: Show a "compare" toggle. When active, display two columns side-by-side: the historical snapshot (left) and the current state (right), with cells highlighted where values differ significantly (health score changed by > 0.1).
5. **FR-2.5**: If the selected timestamp predates available Delta history (table has been vacuumed), display a clear error: "No data available for this timestamp. Delta Lake history is retained for N days."
6. **FR-2.6**: Display the SQL query used (collapsible) so demo attendees can see the `TIMESTAMP AS OF` syntax.

### FR-3: Event Forensics Drill-Down

1. **FR-3.1**: On the Analytics page health scores table, add a "Investigate" button per asset row.
2. **FR-3.2**: Clicking "Investigate" navigates to `/assets/{id}?from={scored_at - 30min}&to={scored_at + 30min}` -- the asset detail page pre-loaded with a 60-minute window centered on the health score timestamp.
3. **FR-3.3**: The asset detail chart must render a vertical reference line (annotation) at the event timestamp, labeled "Alert" or "Anomaly scored".
4. **FR-3.4**: The tag table below the charts must highlight rows where quality != 192 (non-good quality) within the forensics window.

### FR-4: Data Export

1. **FR-4.1**: Add a "Download CSV" button to the Asset Detail page toolbar (next to the time range selector).
2. **FR-4.2**: The button triggers a download of all tag data for the currently displayed asset and time range.
3. **FR-4.3**: CSV columns: `event_timestamp`, `tag_name`, `tag_value`, `quality`, `sdt_compressed`.
4. **FR-4.4**: The backend must stream the CSV response (not buffer entire result in memory) for large exports. Set `Content-Disposition: attachment; filename="{asset_id}_{from}_{to}.csv"`.
5. **FR-4.5**: For exports exceeding 100,000 rows, the backend must return HTTP 413 with a message suggesting a narrower time range. This prevents warehouse overload during demos.
6. **FR-4.6**: Add a "Download CSV" button to the Analytics health scores table for exporting the current or historical fleet snapshot.

### FR-5: Backend API Additions

1. **FR-5.1**: `GET /api/assets/{asset_id}/tags` -- extend existing endpoint to accept `from` (ISO 8601) and `to` (ISO 8601) query parameters as an alternative to the existing `range` (minutes) parameter. When `from`/`to` are provided, `range` is ignored.
2. **FR-5.2**: Add `resolution` query parameter to `GET /api/assets/{asset_id}/tags` accepting values `raw`, `1m`, `5m`, `15m`, `1h`. When omitted, the backend auto-selects resolution based on the time span (per FR-1.4 rules). When `raw` is specified, no downsampling is applied (capped at 10,000 rows).
3. **FR-5.3**: `GET /api/fleet/snapshot?timestamp=ISO` -- new endpoint. Queries `health_scores` using `SELECT ... FROM {catalog}.{schema}.health_scores TIMESTAMP AS OF '{timestamp}'`. Returns the same schema as `GET /api/analytics/health-scores` plus a `snapshot_timestamp` field in the response metadata.
4. **FR-5.4**: `GET /api/assets/{asset_id}/tags/export?from=ISO&to=ISO&format=csv` -- new endpoint. Returns `text/csv` with streaming response. Validate that `from` < `to` and span <= 30 days.
5. **FR-5.5**: `GET /api/assets/{asset_id}/forensics?event_time=ISO&window_minutes=30` -- new endpoint. Returns raw tag events for the asset within `[event_time - window_minutes, event_time + window_minutes]`. Response includes an `event_time` field in metadata for the frontend to draw the reference line.
6. **FR-5.6**: All new endpoints must use the existing `query_service.execute()` pattern with parameterized SQL (no string interpolation of user input). All new query builders must be registered in `QUERY_BUILDERS` dict in `query.py`.
7. **FR-5.7**: All new endpoints must return the standard `{data, meta}` response envelope via the existing `helpers.wrap()` function.

## Non-Functional Requirements

1. **NFR-1 (Performance)**: Downsampled queries for 7-day ranges must complete within 15 seconds on a Small SQL warehouse. The auto-resolution logic exists specifically to bound query cost.
2. **NFR-2 (Performance)**: `TIMESTAMP AS OF` queries must complete within 10 seconds. If the Delta table has been vacuumed past the requested timestamp, the backend must catch the `DELTA_TABLE_NOT_FOUND_AT_VERSION` error and return HTTP 404 with a user-friendly message (not a raw stack trace).
3. **NFR-3 (Security)**: CSV export endpoint must not allow SQL injection. All query parameters must be bound via `StatementParameterListItem`, consistent with existing query patterns.
4. **NFR-4 (Accessibility)**: Date-time picker must be keyboard-navigable. Custom range inputs must have proper `aria-label` attributes.
5. **NFR-5 (Scalability)**: CSV export is capped at 100K rows (FR-4.5). Downsampled queries return at most ~8,640 data points (30 days / 5-min buckets). These caps prevent runaway warehouse costs during demos.
6. **NFR-6 (Compatibility)**: The existing `range` query parameter on `GET /api/assets/{id}/tags` must continue to work unchanged for backward compatibility. The `from`/`to` parameters are additive.

## Acceptance Criteria

### Extended Time Range (FR-1)

1. **AC-1**: Given the Asset Detail page, when the user clicks the "1h" button, then the chart displays tag data from the last 60 minutes (unchanged from current behavior).
2. **AC-2**: Given the Asset Detail page, when the user clicks "24h", then the backend returns 1-minute averaged data points and the chart X-axis shows "HH:MM" labels.
3. **AC-3**: Given the Asset Detail page, when the user selects "Custom" and enters a `from` and `to` datetime, then the chart displays data for exactly that range.
4. **AC-4**: Given a custom range of 3 days, when the backend query executes, then the SQL contains `WINDOW` / time bucketing logic producing 15-minute averaged rows.
5. **AC-5**: Given the Asset Detail page at `/assets/bess01?from=2026-03-20T10:00:00Z&to=2026-03-20T12:00:00Z`, when the page loads, then the time range selector pre-populates with those values and the chart shows data for that range.

### Point-in-Time Fleet Snapshot (FR-2)

6. **AC-6**: Given the Analytics page, when the user enters a timestamp of 2 hours ago and clicks "Show snapshot", then the health scores table displays values from that point in time.
7. **AC-7**: Given a snapshot request, when the backend query executes, then the SQL statement contains `TIMESTAMP AS OF` with the user-provided timestamp.
8. **AC-8**: Given a timestamp older than the Delta retention period, when the user requests a snapshot, then the UI displays an error message mentioning Delta Lake history retention (not a generic 500 error).
9. **AC-9**: Given the compare toggle is active, when a snapshot is loaded, then the page shows historical values on the left and current values on the right, with health score deltas > 0.1 highlighted.
10. **AC-10**: Given a fleet snapshot is displayed, when the user expands "Show SQL", then the collapsible section shows the exact `SELECT ... TIMESTAMP AS OF ...` query that was executed.

### Event Forensics (FR-3)

11. **AC-11**: Given the health scores table on Analytics, when the user clicks "Investigate" on an asset with `scored_at = 2026-03-24T14:30:00Z`, then the browser navigates to `/assets/{id}?from=2026-03-24T14:00:00Z&to=2026-03-24T15:00:00Z`.
12. **AC-12**: Given the Asset Detail page loaded via forensics navigation, when the chart renders, then a vertical dashed line appears at the `event_time` position on the X-axis with a label.
13. **AC-13**: Given the forensics window, when the tag table renders, then rows with `quality != 192` have a red/amber background highlight.

### Data Export (FR-4)

14. **AC-14**: Given the Asset Detail page showing a 1-hour range, when the user clicks "Download CSV", then the browser downloads a file named `{asset_id}_{from}_{to}.csv`.
15. **AC-15**: Given the downloaded CSV, when opened, then it contains columns `event_timestamp,tag_name,tag_value,quality,sdt_compressed` with data matching the chart's time range.
16. **AC-16**: Given an export request that would return > 100,000 rows, when the backend processes it, then it returns HTTP 413 with a JSON body containing an error message.

### Backend API (FR-5)

17. **AC-17**: Given `GET /api/assets/bess01/tags?from=2026-03-24T10:00:00Z&to=2026-03-24T12:00:00Z`, when executed, then the response contains tag data within that range with auto-selected 1-minute resolution.
18. **AC-18**: Given `GET /api/assets/bess01/tags?from=2026-03-24T10:00:00Z&to=2026-03-24T12:00:00Z&resolution=raw`, when executed, then the response contains raw (non-downsampled) data capped at 10,000 rows.
19. **AC-19**: Given `GET /api/fleet/snapshot?timestamp=2026-03-24T12:00:00Z`, when the Delta table has data at that version, then the response contains health scores as of that timestamp with `snapshot_timestamp` in `meta`.
20. **AC-20**: Given `GET /api/assets/bess01/tags/export?from=2026-03-24T10:00:00Z&to=2026-03-24T12:00:00Z&format=csv`, when executed, then the response has `Content-Type: text/csv` and `Content-Disposition` header with the filename.
21. **AC-21**: Given `GET /api/assets/bess01/forensics?event_time=2026-03-24T14:30:00Z&window_minutes=30`, when executed, then the response contains tag events from 14:00 to 15:00 with `event_time` in the `meta` object.
22. **AC-22**: Given any new endpoint receives a malformed ISO timestamp (e.g., `?from=not-a-date`), when the request is processed, then the API returns HTTP 422 with a validation error message.

## Out of Scope

- **Real-time streaming updates for historical ranges**: When viewing a historical custom range, the chart does not live-poll. Live polling only applies when the `to` boundary is "now" (i.e., preset ranges like 5m, 1h, etc.).
- **Multi-asset overlay**: Comparing tag values from two different assets on the same chart is not included. Each asset detail page shows only its own tags.
- **Parquet/JSON export formats**: Only CSV is supported in this iteration.
- **Alert/anomaly management**: This PRD covers read-only forensics (viewing events around an anomaly). Creating, acknowledging, or escalating alerts is not in scope.
- **Custom downsampling functions**: Only time-bucketed AVG is implemented. MIN/MAX/LAST aggregations are deferred.
- **PostgreSQL (Lakebase) time travel**: Time travel features apply only to Delta Lake tables. The Lakebase sink does not support `TIMESTAMP AS OF`.
- **Retention policy configuration**: The PRD does not add UI for configuring Delta table `VACUUM` retention. The app reports the current retention limit but does not change it.

## Dependencies

| Dependency | Type | Notes |
|---|---|---|
| Delta Lake time travel | Platform | Tables must not have been vacuumed past the requested timestamp. Default retention is 30 days. |
| `health_scores` materialized view | Pipeline | Must be populated by the SDP ETL pipeline (`agl-etl`). Fleet snapshot queries this table. |
| `parsed_tags` streaming table | Pipeline | Preferred source for tag queries when `USE_PARSED_TAGS=true`. Falls back to `raw_tags` CTE. |
| Databricks SQL Warehouse | Infrastructure | All queries run via Statement Execution API. Warehouse must be running. |
| Recharts | Frontend | Existing charting library. Reference lines are supported natively via `<ReferenceLine>`. |
| Date picker library | Frontend (new) | Need a date-time picker component. Options: `react-datepicker` (lightweight, widely used) or a headless UI approach with `@headlessui/react` + custom inputs. Decision recorded in Open Questions. |

## Open Questions

1. **Date picker library choice**: Should we use `react-datepicker` (simple, 30KB gzipped, full-featured) or build a minimal picker from native `<input type="datetime-local">` (zero-dependency but inconsistent browser UX)? Recommend `react-datepicker` for demo polish.
2. **Delta retention visibility**: Should the fleet snapshot UI show the available time travel range (earliest available version timestamp) proactively, or only surface it as an error? Showing it proactively is better UX but requires an additional `DESCRIBE HISTORY` query.
3. **Row cap for raw resolution**: FR-5.2 caps raw queries at 10,000 rows. Is this sufficient for forensics windows (typically 30 min of data for one asset)? At 1 event/sec with 20 tags, 30 min = 36,000 rows. Consider raising to 50,000 or making forensics exempt from the cap.
4. **Timezone handling**: Should the date-time picker default to the user's browser timezone or UTC? OT systems typically use UTC. Recommend UTC with a timezone label, and a toggle to switch to local time for display.

## Technical Notes

### Backend: New query builders (in `demo/app/backend/services/query.py`)

Register the following in the `QUERY_BUILDERS` dict:

| Query name | Function | Parameters |
|---|---|---|
| `assetTagsRange` | `_asset_tags_range()` | `asset_id: str`, `from_ts: str`, `to_ts: str`, `resolution: str \| None`, `tags: list[str] \| None` |
| `fleetSnapshot` | `_fleet_snapshot()` | `timestamp: str` |
| `assetTagsExport` | `_asset_tags_export()` | `asset_id: str`, `from_ts: str`, `to_ts: str` |
| `assetForensics` | `_asset_forensics()` | `asset_id: str`, `event_time: str`, `window_minutes: int` |

**Downsampling SQL pattern** (for `assetTagsRange`):
```sql
{_event_cte()},
bucketed AS (
  SELECT
    DATE_TRUNC('{resolution}', event_timestamp) AS bucket,
    tag_name,
    AVG(tag_value) AS tag_value,
    MAX(quality) AS quality,
    BOOL_OR(sdt_compressed) AS sdt_compressed
  FROM events
  WHERE asset_id = :p_asset_id
    AND event_timestamp >= :p_from
    AND event_timestamp <= :p_to
  GROUP BY 1, 2
)
SELECT bucket AS event_timestamp, tag_name, tag_value, quality, sdt_compressed
FROM bucketed
ORDER BY event_timestamp
```

Note: `DATE_TRUNC` accepts `'minute'`, `'hour'`, etc. For 5-minute and 15-minute buckets, use: `TIMESTAMP_SECONDS(FLOOR(UNIX_TIMESTAMP(event_timestamp) / {seconds}) * {seconds})` instead.

**Fleet snapshot SQL pattern** (for `fleetSnapshot`):
```sql
SELECT scored_at, asset_id, health_score, primary_risk_tag,
       risk_description, anomaly_tags, estimated_hours_to_failure
FROM {catalog}.{schema}.health_scores TIMESTAMP AS OF :p_timestamp
ORDER BY health_score ASC
```

**Error handling for vacuumed versions**: Catch `QueryError` where the message contains `DELTA_TABLE_NOT_FOUND_AT_VERSION` or `VERSION_NOT_FOUND` and return HTTP 404 with a structured error.

### Backend: New route file

Create `demo/app/backend/routes/time_travel.py` with:
- `GET /api/fleet/snapshot`
- `GET /api/assets/{asset_id}/tags/export`
- `GET /api/assets/{asset_id}/forensics`

Register in `demo/app/backend/main.py` alongside existing routers.

Extend existing `demo/app/backend/routes/assets.py`:
- Modify `get_asset_tags()` to accept `from`, `to`, `resolution` query parameters.

### Frontend: New/modified files

| File | Change |
|---|---|
| `demo/app/frontend/src/components/TimeRangeSelector.tsx` | **New**. Shared component: preset buttons + custom date-time picker. Emits `{ from: string, to: string, preset?: string }`. |
| `demo/app/frontend/src/pages/AssetDetail.tsx` | Replace `TimeRange` type and button group with `<TimeRangeSelector>`. Read/write URL query params. Add CSV download button. Add `<ReferenceLine>` for forensics. |
| `demo/app/frontend/src/pages/Analytics.tsx` | Add Fleet Snapshot section with date-time picker, snapshot table, compare toggle, "Show SQL" collapsible, and "Investigate" buttons on health rows. |
| `demo/app/frontend/src/services/api.ts` | Add `getAssetTagsRange()`, `getFleetSnapshot()`, `exportAssetTagsCsv()`, `getForensics()` functions and corresponding TypeScript interfaces. |
| `demo/app/frontend/src/components/Sidebar.tsx` | No change needed -- Analytics and Asset Detail routes already exist. |

### Frontend: URL query parameter encoding

The `AssetDetail` page must sync its time range state with URL search params:
```
/assets/bess01?range=5m            -- preset
/assets/bess01?from=ISO&to=ISO     -- custom range
/assets/bess01?from=ISO&to=ISO&event_time=ISO  -- forensics mode
```

Use `useSearchParams` from `react-router-dom` to read/write these. When `event_time` is present, render the `<ReferenceLine>` annotation on charts.

### Data model impact

No new tables or schema changes. All features query existing tables (`raw_tags` / `parsed_tags`, `health_scores`, `asset_hierarchy`). The `TIMESTAMP AS OF` clause is a Delta Lake read-time feature that requires no DDL changes.
