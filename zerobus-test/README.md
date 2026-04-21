# Zerobus connectivity test

Tests Zerobus Ingest SDK (gRPC + OAuth M2M) from your machine: create a stream and send 10 JSON records. Use this to verify Zerobus endpoint, workspace URL, and SP credentials **without** going through the Ignition gateway.

**Documentation flow: create the table first, then run the SDK.**

## Recommended: create table then run test (from repo root)

From the repo root, with `.env` containing `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET`:

```bash
make zerobus-test
```

This will:

1. **Create the table** — `make zerobus-test-table` (or run `make zerobus-test` which depends on it) creates `agl_demo.ot.zerobus_test` via the Databricks Statement Execution API (uses `DATABRICKS_CONFIG_PROFILE`, e.g. `daveok`). Ensure catalog/schema exist first (`make db-setup-sql`).
2. **Run the SDK test** — Loads `.env`, sets `ZEROBUS_TARGET_TABLE=agl_demo.ot.zerobus_test`, and runs `zerobus-test/test_zerobus.py`.

Override catalog/schema with: `CATALOG=my_catalog SCHEMA=my_schema make zerobus-test`.

## Create table only

```bash
make zerobus-test-table
```

Or manually with the Databricks SDK (from repo root):

```bash
DATABRICKS_CONFIG_PROFILE=daveok CATALOG=agl_demo SCHEMA=ot DATABRICKS_WAREHOUSE_ID=e4082fdb7ea19a15 \
  uv run --with databricks-sdk python onboarding/databricks/create_zerobus_test_table.py
```

Or run the SQL in a Databricks notebook/SQL editor:

```sql
CREATE TABLE IF NOT EXISTS agl_demo.ot.zerobus_test (
  device_name STRING,
  temp        DOUBLE,
  humidity    DOUBLE
);
```

## Run SDK test with env vars (after table exists)

```bash
export DATABRICKS_CLIENT_ID="<your-sp-client-id>"
export DATABRICKS_CLIENT_SECRET="<your-sp-client-secret>"
# Optional: override endpoint/workspace/table
export DATABRICKS_HOST="https://adb-<workspace-id>.10.azuredatabricks.net"
export ZEROBUS_ENDPOINT="<workspace-id>.zerobus.eastus2.azuredatabricks.net"
export ZEROBUS_TARGET_TABLE="agl_demo.ot.zerobus_test"

cd zerobus-test && uv run python test_zerobus.py
```

Or load from `.env` and use the table created above (from repo root):

```bash
export $(grep -v '^#' .env | xargs)
export ZEROBUS_TARGET_TABLE=agl_demo.ot.zerobus_test
cd zerobus-test && uv run python test_zerobus.py
```

## Run with [agl-demo] profile from ~/.databrickscfg

```bash
cd zerobus-test && uv run python run_with_profile.py
```

Uses `SP_PROFILE_NAME` (default `agl-demo`). Requires the table to exist (run `make zerobus-test-table` first).

## 401 Unauthorized

- Run `make db-check-sp` from the repo root to verify the SP profile and secret (basic workspace auth).
- If that passes but the Zerobus test still returns 401, the SP may need Zerobus direct-write scope or the workspace may use a different OIDC configuration for Zerobus.

## Relation to Ignition and Error 1521

This test uses **JSON** records and a **separate** table (`zerobus_test`). The Ignition module sends **OTEvent protobuf** to `raw_tags`. A passing test confirms SDK + endpoint + OAuth work for that table; it does **not** prove the `raw_tags` table or OTEvent schema. For **Stream creation failed: INTERNAL / 1521** on the gateway, see the repo root [CLAUDE.md](../CLAUDE.md) section "Double-check before configure (stream creation / Error 1521)" and [module/SCHEMA_ALIGNMENT.md](../module/SCHEMA_ALIGNMENT.md).
