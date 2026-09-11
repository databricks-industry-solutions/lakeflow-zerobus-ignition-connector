# LakeTS-compatible Lakebase sink — proposal & reference implementation

**Status:** working reference implementation, validated end-to-end (build + live Lakebase + dockerized gateway) and refined through customer (HIO) field testing. The branch now also carries the Lakebase config UI, restart-persistence of the new fields, and a save-time guard (see **Files changed** and **Known issues & maintainer follow-ups**). Offered to the maintainers for review/integration.
**Branch:** `lakets-chronotable-sink`
**Author context:** Databricks Field Engineering (customer: iron-ore OT/Ignition + LakeTS on Lakebase). Maintainers are in Australia; parallel BHP time-series interest.

---

## Why

Customers want Ignition tag data in **Lakebase via [LakeTS](https://github.com/databricks-solutions/lakets)** (ChronoTables) specifically for **live HMI/current-value reads and low-latency operational dashboards** — a workload the lakehouse can't serve at the required latency but LakeTS-on-Lakebase can.

Today the `sinkMode=lakebase` INSERT is physically incompatible with a LakeTS ChronoTable, for two reasons, both localized to `PostgresClientManager`:

1. **Timestamps are written as BIGINT epoch-microseconds.** A ChronoTable's partition key must be a real `TIMESTAMPTZ` — it can't partition on a bigint.
2. **`ON CONFLICT (event_id)`** targets a single column. A partitioned table requires the partition key in every unique constraint, so the dedupe key must be `(event_time, event_id)`.

The current community workaround is an **adapter table + per-row routing trigger** (`raw_tags` → trigger converts micros→timestamptz and forwards into the ChronoTable). It works, but it adds a third per-row trigger to the write path, an always-empty table to operate, and a trigger to maintain across LakeTS upgrades. Both incompatibilities are ~localized connector changes instead — this is the "≈10-line change" the workaround guide's own "what was deliberately not done" section anticipates.

## What this change adds

Three **opt-in** config knobs on `ConfigModel`, all defaulting to **current behavior** (zero change for existing Zerobus/Lakebase-raw users):

| Config field | Default | LakeTS value | Effect |
|---|---|---|---|
| `postgresTimestampMode` | `EPOCH_MICROS` | `TIMESTAMPTZ` | Wraps the two epoch-micros binds in `to_timestamp(?/1000000.0)` so `event_time`/`ingestion_timestamp` land in native `timestamptz` columns. |
| `postgresConflictColumns` | `event_id` | `event_time, event_id` | Configurable `ON CONFLICT (...)` target (composite key required by a partitioned table). |
| `postgresNullUnusedValueColumns` | `false` | `true` | Writes SQL `NULL` into the typed value columns that don't match the event's `data_type` (kills the misleading `numeric_value=0.0` on BOOLEAN/STRING tags). |

The connector still **binds** epoch-microseconds in all modes; only the SQL text differs. Parameter order and the 18-bind count are identical in both modes, so the bind loop is untouched. `postgresConflictColumns` is validated as a comma-separated identifier list (defense-in-depth; it's admin config, not per-event data).

With these set, the connector writes **directly** into a LakeTS ChronoTable — **no adapter table, no routing trigger.**

## Files changed (branch `lakets-chronotable-sink`)

- `module/src/main/java/.../ConfigModel.java` — 3 opt-in fields + getters/setters + `requiresRestart()`/`updateFrom()` wiring + new enum `PostgresTimestampMode`; plus a `validate()` guard that rejects `TIMESTAMPTZ` without `event_time` in the conflict columns.
- `module/src/main/java/.../PostgresClientManager.java` — `INSERT_SQL` constant → `buildInsertSql(ConfigModel)`; null-coercion in the bind loop.
- `module/src/main/java/.../ZerobusSettings83.java` (8.3) and `.../ZerobusSettings.java` (8.1) — persist the 3 new fields (SFields + `toConfigModel()`/`fromConfigModel()` mapping). **Required for the settings to survive a gateway/module restart** (see Known issues).
- `module/src/main/resources/web/zerobus-config.html` — Lakebase/PostgreSQL config UI (sink-mode selector + fields); only the *active* sink mode's fields are HTML-`required` (hidden `required` fields were silently blocking the save); selecting `TIMESTAMPTZ` auto-fills the two companion LakeTS settings when they are still at stock defaults.
- `module/src/test/java/.../PostgresInsertSqlTest.java`, `.../ConfigModelValidateTest.java` — unit tests (new).
- `validation/` — the LakeTS-side setup + SQL used to validate against live Lakebase (reference, not shipped).

**Persistence note (important for reviewers):** the `/system/zerobus/config` REST API round-trips `ConfigModel` via Gson, so new fields appear there and in the live in-memory config immediately — but persistence is **not** a Gson blob. It is a field-by-field Ignition `PersistentRecord` (`ZerobusSettings83` for 8.3, `ZerobusSettings` for 8.1) mapped by `toConfigModel()`/`fromConfigModel()`. **Any new `ConfigModel` field must also get a column + mapping in the record, or it is silently dropped on save and reverts to its default on the next restart.** (The initial change missed this and caused a restart regression, now fixed on the branch.)

## Example: point the connector at a LakeTS ChronoTable

LakeTS side (once), no adapter/trigger:
```sql
-- ignition_tag_events: 18 OTEvent columns but event_time/ingestion_timestamp are TIMESTAMPTZ
SELECT lakets.create_chronotable('ignition_tag_events','event_time','1 day');
ALTER TABLE ignition_tag_events ADD CONSTRAINT uq_ite UNIQUE (event_time, event_id);
SELECT lakets.enable_lvc('ignition_tag_events', ARRAY['tag_path'], ARRAY['numeric_value','boolean_value','event_time']);
-- + rollups, tiering, retention as desired; deploy the LakeTS maintenance bundle (partition mgr, rollup refresh).
```

Connector config (REST):
```bash
curl -sX POST http://<gw>:<port>/system/zerobus/config -H 'content-type: application/json' -d '{
  "enabled": true, "sinkMode": "lakebase", "enableZerobusSink": false, "enablePostgresSink": true,
  "postgresHost": "...", "postgresPort": 5432, "postgresDatabase": "databricks_postgres",
  "postgresUser": "...", "postgresPassword": "...",
  "postgresTable": "ignition_tag_events",
  "postgresTimestampMode": "TIMESTAMPTZ",
  "postgresConflictColumns": "event_time, event_id",
  "postgresNullUnusedValueColumns": true
}'
```

Generated INSERT (verified):
```sql
INSERT INTO ignition_tag_events (event_id, event_time, ... , batch_bytes_sent)
VALUES (?, to_timestamp(?/1000000.0), ?, ?, ?, ?, ?, ?, ?, ?, to_timestamp(?/1000000.0), ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (event_time, event_id) DO NOTHING;
```

## Validation performed

1. **Build** — `.modl` builds clean against the real Ignition **8.3.3** SDK (JDK 17).
2. **SQL builder unit logic** — default profile unchanged (`ON CONFLICT (event_id)`, no `to_timestamp`, 18 binds); LakeTS profile converts exactly the 2 time columns, composite conflict, still 18 binds.
3. **DB boundary against live Lakebase** — created a real LakeTS ChronoTable + LVC; fired the exact generated SQL: rows land with correct `timestamptz` (today, not 1970), LVC populates, boolean row's `numeric_value` is NULL (not 0.0), and a fixed-`event_id` replay dedupes (`INSERT 0 1` → `INSERT 0 0`).
4. **End-to-end gateway smoke test** — built `.modl` loaded into a dockerized Ignition 8.3.3 gateway (unsigned-modules dev flow); configured LakeTS profile via REST; injected numeric + boolean events via `/system/zerobus/ingest/batch`; confirmed they routed into a `PARTITION BY RANGE (event_time)` table (proves real timestamptz), with correct null-coercion. Fixed-`event_id` replay dedupes via the composite `ON CONFLICT`.

## Known issues & maintainer follow-ups

- **The module unit-test suite does not compile against the current code and needs repair.** `module/src/test/.../ConfigModelTest.java` and `module/src/test/.../compression/SdtOverrideTest.java` (and at least one more) reference removed SDT-override API (`getSdtOverrides()`, `findMatchingOverride()`) — they predate an SDT refactor. As a result `./gradlew test` fails at `compileTestJava`, and the project builds only via `buildModule` (which skips test compilation). The new `PostgresInsertSqlTest` / `ConfigModelValidateTest` are written against the current API but **won't run until the stale tests are fixed or removed**. Recommend repairing the suite and wiring `test` into CI — the persistence regression below would have been caught by a compiling test suite.
- **New `ConfigModel` fields must be mirrored in the `PersistentRecord` + both mappers** (see the Persistence note above). This is easy to miss and fails silently — the config works until the next restart. A round-trip test (`fromConfigModel` → `toConfigModel` equality) would guard it.
- **8.1 parity is code-complete but not runtime-tested here.** The 3 fields were added to `ZerobusSettings` (8.1) for parity, but this environment only had a live 8.3 gateway — the persistence/guard/UI behaviour was runtime-validated on **8.3** only. Recommend an 8.1 smoke test before release.

## Related upstream findings (separate from this change)

- **`ot_event.proto` comment is wrong:** it says `event_time`/`ingestion_timestamp` are "milliseconds since Unix epoch", but `OtEventMapper` writes `getTime()*1000` = **microseconds**, and `DEPLOYMENT.md` divides by 1e6. The code/deployment are consistent (micros); the proto comment should be corrected to avoid misleading integrators.
- **LakeTS (not this repo):** the stock LVC trigger overwrites unconditionally with no recency guard, so a late store-and-forward replay can clobber a live HMI value with stale data. Worth raising with the LakeTS maintainers (the adapter guide sidesteps it with a guarded trigger; a first-class fix belongs upstream in LakeTS).
