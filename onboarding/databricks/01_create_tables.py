# Databricks notebook source
# MAGIC %md
# MAGIC # Create Databricks Tables for Ignition Zerobus Connector (Bronze + Silver scaffolding)
# MAGIC
# MAGIC This notebook creates:
# MAGIC - Unity Catalog catalog + schema (if needed)
# MAGIC - **Bronze ingestion table**: `ot_events_bronze` (schema matches `module/src/main/proto/ot_event.proto`)
# MAGIC - Optional **Silver scaffolding** tables/views (mapping + normalization)
# MAGIC
# MAGIC Notes:
# MAGIC - The Bronze schema is the ingestion contract. Keep it stable.
# MAGIC - Zerobus requires the target Delta table to be enabled for Zerobus ingest.

# COMMAND ----------

# === EDIT THESE ===
CATALOG = "ignition_demo"
SCHEMA = "tilt_ot"
BRONZE_TABLE = "ot_events_bronze"

# Service Principal UUID (not clientId). Example: "6ff2b11b-fdb8-4c2c-9360-ed105d5f6dcb"
SERVICE_PRINCIPAL_UUID = "<service-principal-uuid>"

FULL_BRONZE = f"{CATALOG}.{SCHEMA}.{BRONZE_TABLE}"
print("Target bronze table:", FULL_BRONZE)

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")

# COMMAND ----------

# Bronze table: must match ot_event.proto (names + types + order)
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {FULL_BRONZE} (
  event_id STRING,
  event_time TIMESTAMP,
  tag_path STRING,
  tag_provider STRING,
  numeric_value DOUBLE,
  string_value STRING,
  boolean_value BOOLEAN,
  quality STRING,
  quality_code INT,
  source_system STRING,
  ingestion_timestamp BIGINT,
  data_type STRING,
  alarm_state STRING,
  alarm_priority INT
)
USING DELTA
TBLPROPERTIES (
  'delta.enableZerobus' = 'true',
  'delta.enableChangeDataFeed' = 'true',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true'
)
""")

print("✅ Bronze ready:", FULL_BRONZE)

# COMMAND ----------

# Grants (optional but recommended)
if SERVICE_PRINCIPAL_UUID and SERVICE_PRINCIPAL_UUID != "<service-principal-uuid>":
    spark.sql(f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{SERVICE_PRINCIPAL_UUID}`")
    spark.sql(f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} TO `{SERVICE_PRINCIPAL_UUID}`")
    spark.sql(f"GRANT SELECT, MODIFY ON TABLE {FULL_BRONZE} TO `{SERVICE_PRINCIPAL_UUID}`")
    print("✅ Granted permissions to:", SERVICE_PRINCIPAL_UUID)
else:
    print("⚠️ Skipping grants. Set SERVICE_PRINCIPAL_UUID first.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Optional: Silver layer scaffolding (recommended)
# MAGIC
# MAGIC Typical Silver pattern:
# MAGIC - `silver_asset_registry`: stable list of assets (site/turbine/etc)
# MAGIC - `silver_signal_mapping`: mapping from `tag_path` → business signal (asset_id, signal_name, unit, scale)
# MAGIC - `silver_events_normalized`: normalized long-form telemetry derived from Bronze + mapping

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.silver_asset_registry (
  asset_id STRING,
  asset_type STRING,
  site STRING,
  display_name STRING,
  active BOOLEAN
)
USING DELTA
""")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.silver_signal_mapping (
  tag_path STRING,
  asset_id STRING,
  signal_name STRING,
  unit STRING,
  scale DOUBLE,
  offset DOUBLE,
  active BOOLEAN
)
USING DELTA
""")

spark.sql(f"""
CREATE OR REPLACE VIEW {CATALOG}.{SCHEMA}.silver_events_normalized AS
SELECT
  b.event_time,
  b.ingestion_timestamp,
  b.source_system,
  m.asset_id,
  m.signal_name,
  m.unit,
  CASE
    WHEN b.numeric_value IS NOT NULL THEN (b.numeric_value * COALESCE(m.scale, 1.0) + COALESCE(m.offset, 0.0))
    WHEN b.boolean_value IS NOT NULL THEN CAST(b.boolean_value AS DOUBLE)
    ELSE NULL
  END AS value_numeric,
  b.string_value,
  b.quality,
  b.quality_code,
  b.tag_path
FROM {FULL_BRONZE} b
LEFT JOIN {CATALOG}.{SCHEMA}.silver_signal_mapping m
  ON b.tag_path = m.tag_path AND m.active = true
""")

print("✅ Silver scaffolding created (tables + view)")


