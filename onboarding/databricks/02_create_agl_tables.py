# Databricks notebook source
# MAGIC %md
# MAGIC # AGL Tomago demo — Create Bronze table in `agl_ignition`
# MAGIC
# MAGIC This notebook creates:
# MAGIC - Unity Catalog catalog + schemas (if needed)
# MAGIC - **Bronze ingestion table**: `agl_ignition.scada_data.tag_events`
# MAGIC
# MAGIC Notes:
# MAGIC - Schema matches `module/src/main/proto/ot_event.proto`
# MAGIC - Zerobus requires the target Delta table to be enabled for Zerobus ingest.

# COMMAND ----------

# === EDIT THESE IF NEEDED ===
CATALOG = "agl_ignition"
SCHEMA = "scada_data"
BRONZE_TABLE = "tag_events"

# Service Principal UUID (not clientId). Example: "6ff2b11b-fdb8-4c2c-9360-ed105d5f6dcb"
SERVICE_PRINCIPAL_UUID = "<service-principal-uuid>"

FULL_BRONZE = f"{CATALOG}.{SCHEMA}.{BRONZE_TABLE}"
print("Target bronze table:", FULL_BRONZE)

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")

# COMMAND ----------

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

if SERVICE_PRINCIPAL_UUID and SERVICE_PRINCIPAL_UUID != "<service-principal-uuid>":
    spark.sql(f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{SERVICE_PRINCIPAL_UUID}`")
    spark.sql(f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} TO `{SERVICE_PRINCIPAL_UUID}`")
    spark.sql(f"GRANT SELECT, MODIFY ON TABLE {FULL_BRONZE} TO `{SERVICE_PRINCIPAL_UUID}`")
    print("✅ Granted permissions to:", SERVICE_PRINCIPAL_UUID)
else:
    print("⚠️ Skipping grants. Set SERVICE_PRINCIPAL_UUID first.")

