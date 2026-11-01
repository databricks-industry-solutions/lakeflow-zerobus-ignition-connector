# LakeTS direct-sink validation

Reference SQL used to validate the `lakets-chronotable-sink` change against a
real LakeTS ChronoTable on Lakebase (see `../LAKETS_DIRECT_SINK.md`). Not shipped
with the module.

- `01_setup_chronotable.sql` — creates `ign_val.ignition_tag_events` as a real
  LakeTS ChronoTable (TIMESTAMPTZ partition key) + composite unique + LVC. No
  `raw_tags` adapter, no routing trigger.
- `02_insert_as_connector.sql` — fires the EXACT INSERT the patched connector
  emits in LakeTS profile (`to_timestamp(?/1e6)` on the two epoch-micros columns,
  `ON CONFLICT (event_time, event_id)`), for a numeric and a boolean tag.
- `03_verify.sql` — asserts timestamptz correctness (not 1970), null-coercion on
  the boolean row, and LVC population.

Dedupe was validated separately by replaying a fixed-`event_id` row
(`INSERT 0 1` then `INSERT 0 0`).

Run against Lakebase, e.g.:
```bash
databricks psql --project <proj> --branch production --endpoint primary -- \
  -d databricks_postgres -f validation/01_setup_chronotable.sql
```
