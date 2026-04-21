# PRD: Virtual / Calculated Tags

**Author:** david.okeeffe | **Date:** 2026-03-24 | **Status:** DRAFT

## Problem Statement

OT engineers working with traditional historians (e.g., OSIsoft PI, Honeywell PHD) routinely define calculated or virtual tags -- derived signals computed from one or more real tags. Examples include net power (active power minus auxiliary load), site-level generation totals, efficiency ratios, and rate-of-change signals.

The Zerobus connector streams raw tag data from Ignition into Delta Lake via `raw_tags`, and the SDP pipeline produces `parsed_tags`, `aggregated_tags`, `enriched_tags`, and `health_scores`. However, there is no mechanism for users to define their own calculated tags through the demo app UI. The existing derived signals (health scores, revenue risk) are hard-coded in the pipeline and not user-configurable.

This gap matters for two reasons:

1. **Demo differentiation** -- Showing that Databricks can replicate a core historian capability (calculated tags) entirely within Unity Catalog + Lakeflow Pipelines, with no proprietary historian engine, is a powerful proof point.
2. **Practical utility** -- OT engineers expect to define virtual tags like `net_power = active_power_mw - aux_load_mw` through a UI and see them appear alongside real tags in asset views and charts.

## User Personas & Stories

- As an **OT engineer**, I want to define a calculated tag using a SQL expression over existing tag values so that I can monitor derived signals (e.g., net power, thermal headroom) without modifying the data source.
- As an **OT engineer**, I want to see calculated tags alongside real tags in the asset detail view so that I have a unified view of all signals for an asset.
- As a **solutions architect**, I want pre-seeded calculated tags that demonstrate common OT use cases out of the box so that I can walk through the demo without manual setup.
- As an **OT engineer**, I want to validate a calculated tag expression against sample data before saving so that I can catch errors early.
- As an **OT engineer**, I want to scope a calculated tag to a template (all assets of a type) or a single asset so that template-level calculations propagate automatically.

## Functional Requirements

### Data Model

1. **FR-1**: A `calculated_tags` table SHALL be created in `{catalog}.{schema}` with the following schema:

   | Column | Type | Constraints | Description |
   |--------|------|-------------|-------------|
   | calc_tag_id | STRING | PK, NOT NULL | Unique identifier (slug format: `[a-z0-9_]+`) |
   | name | STRING | NOT NULL | Machine-readable name (e.g., `net_power`) |
   | display_name | STRING | NOT NULL | Human-readable label (e.g., `Net Power`) |
   | description | STRING | | Free-text description |
   | asset_scope | STRING | NOT NULL | One of: `global`, `template`, `asset` |
   | scope_id | STRING | | `template_id` when scope=template, `asset_id` when scope=asset, NULL when scope=global |
   | expression | STRING | NOT NULL | SQL expression using `{tag_name}` placeholders |
   | input_tags | ARRAY\<STRING\> | NOT NULL | List of source tag names referenced in expression |
   | output_unit | STRING | | Engineering unit of the result (e.g., `MW`, `%/min`) |
   | output_data_type | STRING | NOT NULL, DEFAULT 'DOUBLE' | `DOUBLE`, `INT`, `BOOLEAN`, `STRING` |
   | refresh_mode | STRING | NOT NULL, DEFAULT 'on_change' | `on_change` or `interval` |
   | refresh_interval_seconds | INT | | Seconds between evaluations when refresh_mode=interval |
   | enabled | BOOLEAN | NOT NULL, DEFAULT true | Whether this tag is currently active |
   | created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP() | |
   | updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP() | |

2. **FR-2**: A `calculated_tag_values` table SHALL be created in `{catalog}.{schema}` with the following schema:

   | Column | Type | Constraints | Description |
   |--------|------|-------------|-------------|
   | calc_tag_id | STRING | NOT NULL, FK -> calculated_tags | References the definition |
   | asset_id | STRING | NOT NULL | Asset the value was computed for |
   | event_timestamp | TIMESTAMP | NOT NULL | Timestamp of the source data used |
   | value | DOUBLE | | Computed numeric result |
   | value_str | STRING | | Computed string result (for non-numeric expressions) |

   Clustered by `[event_timestamp, calc_tag_id]`.

### Pre-Seeded Calculated Tags

3. **FR-3**: The setup SQL SHALL seed the following calculated tags via MERGE INTO (idempotent):

   | calc_tag_id | name | expression | scope | input_tags | unit |
   |-------------|------|------------|-------|------------|------|
   | `calc_net_power` | net_power | `{activepower_mw} - {aux_load_mw}` | template: `tpl_bess` | `[telemetry/activepower_mw, telemetry/aux_load_mw]` | MW |
   | `calc_site_total_gen` | site_total_generation | `SUM({activepower_mw})` | global | `[telemetry/activepower_mw]` | MW |
   | `calc_efficiency` | efficiency_ratio | `{output_power} / NULLIF({input_power}, 0)` | template: `tpl_inverter` | `[output_power, input_power]` | ratio |
   | `calc_thermal_headroom` | thermal_headroom | `45.0 - {max_rack_temp_c}` | template: `tpl_bess` | `[thermal/maxracktemp_c]` | C |
   | `calc_soc_roc` | soc_rate_of_change | `({soc_pct} - {soc_pct_5min}) / 5.0` | template: `tpl_bess` | `[telemetry/soc_pct]` | %/min |

4. **FR-4**: `calc_soc_roc` (rate of change) SHALL use a windowed lag function. The expression evaluator SHALL support a `{tag_name_Nmin}` syntax (e.g., `{soc_pct_5min}`) that resolves to the tag's value N minutes ago from `parsed_tags`.

### Expression Language

5. **FR-5**: Expressions SHALL be SQL fragments that are embedded within a controlled `SELECT` statement. Supported operations:
   - Arithmetic: `+`, `-`, `*`, `/`
   - SQL functions: `ABS`, `SQRT`, `ROUND`, `GREATEST`, `LEAST`, `COALESCE`, `NULLIF`, `LOG`, `EXP`, `POWER`
   - Aggregations (for cross-asset scope): `SUM`, `AVG`, `MIN`, `MAX`, `COUNT`
   - Conditionals: `CASE WHEN ... THEN ... ELSE ... END`
   - Literals: numeric constants, string constants

6. **FR-6**: Expressions SHALL NOT allow: DDL/DML keywords (`CREATE`, `DROP`, `ALTER`, `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `GRANT`, `REVOKE`), subqueries (`SELECT` keyword), semicolons, comments (`--`, `/*`), or system functions (`CURRENT_USER`, `SESSION_USER`). The backend SHALL reject expressions containing any blocked token at creation/update time before executing SQL.

7. **FR-7**: Expression placeholders (`{tag_name}`) SHALL be resolved by the backend into column references or subqueries against `parsed_tags`. The backend SHALL validate that all `{tag_name}` placeholders in an expression correspond to tags that exist in `parsed_tags` for at least one asset in the tag's scope. Validation failures SHALL return a 422 response with a list of unresolved tag names.

### Pipeline Integration

8. **FR-8**: A new Lakeflow materialized view named `calculated_tag_latest` SHALL be added to the SDP pipeline (`pipelines/sdp/transformations/calculated_tags.py`). It SHALL:
   - Read enabled rows from `calculated_tags` (definitions).
   - For each definition, evaluate the expression against `parsed_tags` data from the last 10 minutes.
   - Output rows into `calculated_tag_values` with: `calc_tag_id`, `asset_id`, `event_timestamp`, `value`.
   - Respect `asset_scope`: template-scoped tags evaluate for all assets with that `template_id`; asset-scoped tags evaluate for only that asset; global tags evaluate across all assets.

9. **FR-9**: The materialized view SHALL handle expression evaluation errors gracefully. If an expression fails for a specific asset (e.g., division by zero not caught by NULLIF, missing input tags), the row SHALL be omitted from the output rather than failing the entire MV refresh. The MV SHALL log a DLT expectation violation for failed expressions.

### Backend API

10. **FR-10**: The following REST endpoints SHALL be added under `demo/app/backend/routes/calculated_tags.py` with router prefix `/api/calculated-tags`:

    | Method | Path | Description | Request Body | Response |
    |--------|------|-------------|--------------|----------|
    | GET | `/` | List all definitions | - | `{data: CalcTag[], meta}` |
    | POST | `/` | Create a new calculated tag | `CalcTagCreate` | `{data: CalcTag, meta}` (201) |
    | GET | `/{calc_tag_id}` | Get one definition | - | `{data: CalcTag, meta}` |
    | PUT | `/{calc_tag_id}` | Update a definition | `CalcTagUpdate` | `{data: CalcTag, meta}` |
    | DELETE | `/{calc_tag_id}` | Delete a definition | - | `{data: {deleted: id}, meta}` |
    | POST | `/validate` | Validate expression | `{expression, input_tags, scope, scope_id}` | `{data: {valid, errors[], sample_results[]}, meta}` |
    | GET | `/{calc_tag_id}/values` | Get computed values | Query: `from`, `to`, `asset_id` (optional) | `{data: CalcTagValue[], meta}` |

11. **FR-11**: The `POST /validate` endpoint SHALL:
    - Parse the expression and check for blocked tokens (FR-6).
    - Resolve `{tag_name}` placeholders against `parsed_tags`.
    - Execute the expression as a `SELECT` against up to 10 sample rows.
    - Return `{valid: true, sample_results: [{asset_id, value, timestamp}]}` on success.
    - Return `{valid: false, errors: ["message"]}` on failure.

12. **FR-12**: All query builders for calculated tags SHALL be registered in `QUERY_BUILDERS` dict in `demo/app/backend/services/query.py` following the existing pattern (named query builder functions returning `(sql, params)` tuples).

### Frontend UI

13. **FR-13**: A new page `/tags/calculated` SHALL be added at `demo/app/frontend/src/pages/CalculatedTags.tsx`. It SHALL display:
    - A table listing all calculated tags with columns: Name, Expression, Scope, Unit, Enabled, Last Value, Actions (edit/delete).
    - A "New Calculated Tag" button opening a creation form.
    - Inline enable/disable toggle per row.

14. **FR-14**: The creation/edit form SHALL include:
    - Name (slug, auto-generated from display_name).
    - Display name (free text).
    - Expression input with tag name autocomplete (fetched from `parsed_tags` distinct tag names).
    - Scope selector: Global / Template (dropdown of templates) / Asset (dropdown/search of assets).
    - Output unit (free text).
    - A "Validate" button that calls `POST /validate` and displays sample results or errors inline.
    - A "Save" button (disabled until validation passes).

15. **FR-15**: A sidebar navigation item "Calculated Tags" SHALL be added to the "Asset Framework" section in `demo/app/frontend/src/components/Sidebar.tsx`.

### Integration with Asset Detail

16. **FR-16**: The asset detail page (`/assets/{id}`) SHALL display calculated tags alongside real tags. Calculated tags SHALL be visually distinguished with a "calc" badge or a different icon/color in the tag table. The tag table SHALL include a `source` column showing "raw" or "calculated".

17. **FR-17**: Calculated tag values SHALL be plottable in the existing time-series chart alongside real tag values. The chart legend SHALL prefix calculated tag names with "calc:" to distinguish them.

## Non-Functional Requirements

1. **NFR-1 (Security)**: Expression evaluation SHALL use parameterized SQL where possible. The expression itself is a SQL fragment inserted into a controlled `SELECT` template; the blocklist (FR-6) provides defense-in-depth. The backend SHALL never execute user expressions outside of the sandboxed `SELECT` wrapper.

2. **NFR-2 (Performance)**: The `calculated_tag_latest` materialized view SHALL complete a full refresh within 60 seconds for up to 50 calculated tag definitions across 50 assets (2,500 evaluation combinations). The MV refresh cadence is controlled by the SDP pipeline schedule (typically continuous or every 30 seconds).

3. **NFR-3 (Performance)**: The `GET /api/calculated-tags/{id}/values` endpoint SHALL return results within 5 seconds for a 1-hour time range on a SQL warehouse with 1 DBU.

4. **NFR-4 (Idempotency)**: All seed data SQL SHALL use `MERGE INTO` so that re-running setup is safe and does not create duplicates.

5. **NFR-5 (Accessibility)**: The calculated tags UI form SHALL be keyboard-navigable and use proper ARIA labels on the expression input and scope selector.

6. **NFR-6 (Consistency)**: The backend route file SHALL follow the same patterns as `demo/app/backend/routes/asset_framework.py`: Pydantic models for request validation, `query_service.execute()` for all SQL, and `_wrap()` for response formatting.

## Acceptance Criteria

1. **AC-1**: Given a fresh deployment after `make db-setup-sql`, when the user queries `SELECT count(*) FROM {catalog}.{schema}.calculated_tags`, then the result is >= 5 (the pre-seeded calculated tags from FR-3).

2. **AC-2**: Given a running SDP pipeline and simulator generating BESS data, when the `calculated_tag_latest` MV refreshes, then `SELECT * FROM {catalog}.{schema}.calculated_tag_values WHERE calc_tag_id = 'calc_net_power'` returns at least one row per BESS asset with a non-null `value`.

3. **AC-3**: Given the demo app backend is running, when `GET /api/calculated-tags` is called, then the response contains `data` as an array with >= 5 items, each having `calc_tag_id`, `name`, `expression`, `enabled` fields.

4. **AC-4**: Given the demo app backend is running, when `POST /api/calculated-tags` is called with `{"calc_tag_id": "test_tag", "name": "test_tag", "display_name": "Test Tag", "expression": "{activepower_mw} * 2", "input_tags": ["telemetry/activepower_mw"], "asset_scope": "global", "output_data_type": "DOUBLE"}`, then the response status is 201 and the returned object has `calc_tag_id = "test_tag"`.

5. **AC-5**: Given the demo app backend is running, when `POST /api/calculated-tags` is called with an expression containing `DROP TABLE`, then the response status is 422 and `meta.error` contains "blocked".

6. **AC-6**: Given the demo app backend is running, when `POST /api/calculated-tags/validate` is called with `{"expression": "{activepower_mw} - {aux_load_mw}", "input_tags": ["telemetry/activepower_mw", "telemetry/aux_load_mw"], "scope": "template", "scope_id": "tpl_bess"}`, then the response contains `valid: true` and `sample_results` is a non-empty array.

7. **AC-7**: Given the demo app backend is running, when `POST /api/calculated-tags/validate` is called with `{"expression": "{nonexistent_tag} + 1", "input_tags": ["nonexistent_tag"], "scope": "global"}`, then the response contains `valid: false` and `errors` includes a message about unresolved tag names.

8. **AC-8**: Given the demo app frontend is loaded, when the user navigates to `/tags/calculated`, then a table is rendered showing at least the 5 pre-seeded calculated tags with columns for name, expression, scope, and enabled status.

9. **AC-9**: Given the demo app frontend is loaded and a BESS asset has calculated tag values, when the user navigates to `/assets/{bess_asset_id}`, then the tag table includes calculated tags with a visual "calc" badge, and the tag count in the header reflects both real and calculated tags.

10. **AC-10**: Given a calculated tag `calc_net_power` exists and is enabled, when `DELETE /api/calculated-tags/calc_net_power` is called and then `GET /api/calculated-tags/calc_net_power` is called, then the DELETE returns 200 and the subsequent GET returns 404.

11. **AC-11**: Given the demo app backend is running, when `PUT /api/calculated-tags/calc_thermal_headroom` is called with `{"enabled": false}`, then subsequent calls to `GET /api/calculated-tags/calc_thermal_headroom` return `enabled: false`, and the next MV refresh does not compute values for `calc_thermal_headroom`.

12. **AC-12**: Given the calculated tags page is loaded, when the user clicks "New Calculated Tag" and types `{act` in the expression field, then an autocomplete dropdown appears showing tag names matching the prefix (e.g., `telemetry/activepower_mw`).

## Out of Scope

- **Real-time streaming evaluation**: Calculated tags are evaluated via MV refresh (batch), not as a continuous stream. Sub-second freshness is not a goal for this iteration.
- **Complex event processing**: Windowed aggregations beyond simple time-lag (`{tag_Nmin}`) are not supported. Full CEP (e.g., "alert when net_power > threshold for 5 consecutive minutes") is out of scope.
- **Expression versioning/audit trail**: No history of expression changes. A future iteration could use Delta time travel.
- **Cross-site aggregations**: `site_total_generation` is pre-seeded as a demo but cross-site rollups (e.g., fleet total) are not explicitly supported in the MV beyond what SQL naturally allows.
- **Permissions/RBAC on calculated tag definitions**: Any authenticated user of the demo app can create/edit/delete calculated tags. Fine-grained permissions are out of scope.
- **Alerting on calculated tag values**: No threshold-based alerting or notification system.
- **Lakebase (PostgreSQL) sink**: Calculated tag values are stored in Delta Lake only, not replicated to Lakebase.

## Dependencies

- **Unity Catalog**: The `calculated_tags` and `calculated_tag_values` tables require the target catalog/schema to exist (created by `make db-setup-sql`).
- **SDP Pipeline (Lakeflow)**: The `calculated_tag_latest` MV runs within the existing `ot_etl` pipeline. The pipeline must be running for computed values to appear.
- **parsed_tags streaming table**: Expression evaluation reads from `parsed_tags`. The SDP pipeline must be active and `parsed_tags` must be populated.
- **asset_hierarchy + asset_templates tables**: Scope resolution for template-scoped and asset-scoped tags requires these tables (already exist).
- **Service Principal grants**: The SP needs `MODIFY` and `SELECT` on the two new tables. Must be added to `setup_uc_functions.sql` or `run_setup_sql.py`.
- **databricks.yml**: The new pipeline transformation file (`calculated_tags.py`) is auto-discovered via the existing glob pattern `./pipelines/sdp/transformations/**`.

## Open Questions

1. **Rate-of-change lag resolution**: Should the `{tag_Nmin}` syntax use a LAG window function on `parsed_tags` ordered by `event_timestamp`, or query a separate time-bucketed table? LAG on `parsed_tags` may be expensive if the table is large. A simpler approach for V1: precompute the lag value in the MV's CTE with a `MAX(tag_value) FILTER (WHERE event_timestamp BETWEEN ... AND ...)` window.

2. **MV vs. Streaming Table**: Should `calculated_tag_latest` be a materialized view (batch refresh, simpler) or a streaming table reading from `parsed_tags` (lower latency but more complex expression evaluation in streaming context)? Recommendation: start with MV for simplicity; migrate to streaming table if refresh latency is unacceptable.

3. **Expression sandbox strength**: The blocklist approach (FR-6) is defense-in-depth for a demo app. For a production feature, should expressions be parsed into an AST and validated structurally? Recommendation: blocklist is sufficient for demo scope; document the limitation.

4. **Tag autocomplete source**: Should autocomplete fetch distinct `tag_name` values from `parsed_tags` (large scan) or from `template_attributes.tag_pattern` (small, pre-defined)? Recommendation: use `template_attributes` first, fall back to a `LIMIT 100` distinct query on `parsed_tags` with a prefix filter.

## Technical Notes

### New Files

| Path | Purpose |
|------|---------|
| `pipelines/sql/setup_calculated_tags.sql` | DDL + seed data for `calculated_tags` and `calculated_tag_values` tables |
| `pipelines/sdp/transformations/calculated_tags.py` | Lakeflow MV definition for `calculated_tag_latest` |
| `demo/app/backend/routes/calculated_tags.py` | FastAPI router with CRUD + validate endpoints |
| `demo/app/frontend/src/pages/CalculatedTags.tsx` | Calculated tags list + create/edit page |
| `demo/app/frontend/src/components/ExpressionEditor.tsx` | Expression input with tag autocomplete |
| `demo/app/backend/tests/test_calculated_tags.py` | Backend unit tests for expression validation and CRUD |
| `demo/app/frontend/src/__tests__/pages/CalculatedTags.test.tsx` | Frontend component tests |

### Modified Files

| Path | Change |
|------|--------|
| `demo/app/backend/main.py` | Import and include `calculated_tags.router` |
| `demo/app/backend/services/query.py` | Add query builders to `QUERY_BUILDERS` dict: `calcTagsList`, `calcTagById`, `calcTagCreate`, `calcTagUpdate`, `calcTagDelete`, `calcTagValidate`, `calcTagValues`, `calcTagDistinctInputTags` |
| `demo/app/frontend/src/App.tsx` | Add route for `/tags/calculated` |
| `demo/app/frontend/src/components/Sidebar.tsx` | Add "Calculated Tags" to `assetFrameworkLinks` |
| `demo/app/frontend/src/pages/AssetDetail.tsx` | Fetch and display calculated tag values alongside real tags |
| `demo/app/frontend/src/services/api.ts` | Add API client methods for calculated tag endpoints |
| `pipelines/sql/setup_tables.sql` or `onboarding/run_setup_sql.py` | Include `setup_calculated_tags.sql` in the setup sequence |
| `databricks.yml` | No change needed -- glob pattern already covers new `.py` file in `transformations/` |

### Expression Evaluation SQL Template

The backend generates SQL like:

```sql
WITH source_data AS (
  SELECT
    asset_id,
    event_timestamp,
    MAX(CASE WHEN tag_name = 'telemetry/activepower_mw' THEN tag_value END) AS activepower_mw,
    MAX(CASE WHEN tag_name = 'telemetry/aux_load_mw' THEN tag_value END) AS aux_load_mw
  FROM {catalog}.{schema}.parsed_tags
  WHERE event_timestamp >= TIMESTAMPADD(MINUTE, -10, CURRENT_TIMESTAMP())
    AND tag_name IN ('telemetry/activepower_mw', 'telemetry/aux_load_mw')
    AND asset_id IN (/* scope-filtered asset list */)
  GROUP BY asset_id, event_timestamp
)
SELECT
  asset_id,
  event_timestamp,
  (activepower_mw - aux_load_mw) AS value
FROM source_data
WHERE activepower_mw IS NOT NULL AND aux_load_mw IS NOT NULL
```

The `{tag_name}` placeholders in the user expression are replaced with sanitized column aliases, and the PIVOT-style CTE ensures each tag becomes a column. This approach:
- Prevents SQL injection (tag names are matched via parameterized `IN` clause, not string interpolation).
- Keeps the user expression as a column expression within a controlled `SELECT`.
- Handles NULL gracefully (WHERE clause filters incomplete rows).

### Query Builder Function Signatures

```python
# In demo/app/backend/services/query.py

def _calc_tags_list() -> tuple[str, list[Any]]:
    ...

def _calc_tag_by_id(calc_tag_id: str) -> tuple[str, list[Any]]:
    ...

def _calc_tag_create(
    calc_tag_id: str, name: str, display_name: str, description: str | None,
    asset_scope: str, scope_id: str | None, expression: str,
    input_tags: list[str], output_unit: str | None, output_data_type: str,
    refresh_mode: str, refresh_interval_seconds: int | None, enabled: bool,
) -> tuple[str, list[Any]]:
    ...

def _calc_tag_update(
    calc_tag_id: str, display_name: str | None, description: str | None,
    expression: str | None, input_tags: list[str] | None,
    output_unit: str | None, enabled: bool | None,
) -> tuple[str, list[Any]]:
    ...

def _calc_tag_delete(calc_tag_id: str) -> tuple[str, list[Any]]:
    ...

def _calc_tag_validate(
    expression: str, input_tags: list[str], scope: str, scope_id: str | None,
) -> tuple[str, list[Any]]:
    ...

def _calc_tag_values(
    calc_tag_id: str, from_ts: str | None, to_ts: str | None,
    asset_id: str | None,
) -> tuple[str, list[Any]]:
    ...
```

### Pydantic Models (Backend)

```python
# In demo/app/backend/routes/calculated_tags.py

class CalcTagCreate(BaseModel):
    calc_tag_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    asset_scope: str = Field(pattern=r"^(global|template|asset)$")
    scope_id: str | None = None
    expression: str = Field(min_length=1, max_length=2000)
    input_tags: list[str] = Field(min_length=1)
    output_unit: str | None = None
    output_data_type: str = Field(default="DOUBLE", pattern=r"^(DOUBLE|INT|BOOLEAN|STRING)$")
    refresh_mode: str = Field(default="on_change", pattern=r"^(on_change|interval)$")
    refresh_interval_seconds: int | None = None
    enabled: bool = True

class CalcTagUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    expression: str | None = Field(default=None, max_length=2000)
    input_tags: list[str] | None = None
    output_unit: str | None = None
    output_data_type: str | None = Field(default=None, pattern=r"^(DOUBLE|INT|BOOLEAN|STRING)$")
    refresh_mode: str | None = Field(default=None, pattern=r"^(on_change|interval)$")
    refresh_interval_seconds: int | None = None
    enabled: bool | None = None

class CalcTagValidateRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=2000)
    input_tags: list[str] = Field(min_length=1)
    scope: str = Field(pattern=r"^(global|template|asset)$")
    scope_id: str | None = None
```
