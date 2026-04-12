# Databricks notebook source
# MAGIC %md
# MAGIC # Historical Data Backfill
# MAGIC Generates 7 days of synthetic OT tag events into `raw_tags` matching the
# MAGIC Zerobus protobuf schema. Populates data for time-travel, fleet snapshot,
# MAGIC and forensics demo features.

# COMMAND ----------

import math
import random
import uuid
from datetime import datetime, timedelta, timezone

try:
    dbutils.widgets.text("days", "7")
    dbutils.widgets.text("interval_sec", "300")
    dbutils.widgets.text("catalog", "ot_demo")
    dbutils.widgets.text("schema", "ot")
    BACKFILL_DAYS = int(dbutils.widgets.get("days"))
    BACKFILL_INTERVAL_SEC = int(dbutils.widgets.get("interval_sec"))
    CATALOG = dbutils.widgets.get("catalog")
    SCHEMA = dbutils.widgets.get("schema")
except Exception:
    BACKFILL_DAYS = 7
    BACKFILL_INTERVAL_SEC = 300
    CATALOG = "ot_demo"
    SCHEMA = "ot"

TABLE = f"{CATALOG}.{SCHEMA}.raw_tags"
end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
start = end - timedelta(days=BACKFILL_DAYS)

print(f"Backfill: {start:%Y-%m-%d %H:%M} → {end:%Y-%m-%d %H:%M} UTC")
print(f"Interval: {BACKFILL_INTERVAL_SEC}s | Target: {TABLE}")

# COMMAND ----------

# Sites, providers, and tag profiles
# Tag path format: [provider]AGL/Australia/Region/Location/SiteXX/AssetXX/Subsystem/Signal

SITES = [
    {"name": "Tomago", "region": "NSW", "state": "NSW"},
    {"name": "Liddell", "region": "NSW", "state": "NSW"},
    {"name": "BrokenHill", "region": "NSW", "state": "NSW"},
    {"name": "Callide", "region": "QLD", "state": "QLD"},
    {"name": "Gladstone", "region": "QLD", "state": "QLD"},
]

# (subsystem, signal, base, amplitude, pattern, noise)
BESS_TAGS = [
    ("Battery", "SoC_pct", 50.0, 40.0, "sin", 2.0),
    ("Battery", "SoH_pct", 95.0, 3.0, "sin", 0.5),
    ("Battery", "Voltage_V", 400.0, 15.0, "sin", 1.0),
    ("Battery", "Current_A", 0.0, 300.0, "sin", 10.0),
    ("Battery", "Temperature_C", 28.0, 8.0, "sin", 1.0),
    ("Battery", "ChargeRate_pct", 50.0, 45.0, "sin", 3.0),
    ("Battery", "DischargeRate_pct", 50.0, 45.0, "sin", 3.0),
    ("Inverter", "Power_kW", 250.0, 200.0, "sin", 15.0),
    ("Inverter", "Frequency_Hz", 50.0, 0.3, "sin", 0.02),
    ("Inverter", "Efficiency_pct", 95.0, 3.0, "sin", 0.5),
    ("Thermal", "CoolantTemp_C", 25.0, 6.0, "sin", 0.5),
    ("Thermal", "AmbientTemp_C", 22.0, 10.0, "sin", 1.0),
    ("Status", "OperationalState", 1.0, 0.0, "const", 0.0),
    ("Status", "AlarmCode", 0.0, 0.0, "const", 0.0),
    ("Status", "Mode", 1.0, 0.0, "const", 0.0),
    ("Status", "CoolingActive", 1.0, 0.0, "const", 0.0),
]

WIND_TAGS = [
    ("Generator", "Speed_RPM", 900.0, 600.0, "sin", 30.0),
    ("Generator", "Power_kW", 2500.0, 2000.0, "sin", 100.0),
    ("Generator", "Torque_Nm", 25000.0, 15000.0, "sin", 500.0),
    ("Rotor", "BladePitch_deg", 12.0, 10.0, "walk", 1.0),
    ("Rotor", "WindSpeed_ms", 12.0, 8.0, "sin", 1.5),
    ("Rotor", "RotorRPM", 10.0, 6.0, "sin", 0.5),
    ("Nacelle", "YawAngle_deg", 180.0, 90.0, "walk", 5.0),
    ("Nacelle", "Temperature_C", 35.0, 15.0, "sin", 1.0),
    ("Grid", "Voltage_V", 400.0, 15.0, "sin", 1.0),
    ("Grid", "Frequency_Hz", 50.0, 0.3, "sin", 0.02),
    ("Grid", "ReactivePower_kVAR", 0.0, 500.0, "sin", 30.0),
    ("Status", "OperationalState", 1.0, 0.0, "const", 0.0),
    ("Status", "AlarmCode", 0.0, 0.0, "const", 0.0),
    ("Turbine", "Mode", 1.0, 0.0, "const", 0.0),
    ("Grid", "FaultDetected", 0.0, 0.0, "const", 0.0),
]

# COMMAND ----------

# Anomaly + value generation

def gen_anomaly_windows(start, end, count=3):
    span = (end - start).total_seconds()
    windows = []
    for _ in range(count):
        offset = random.uniform(0.1 * span, 0.9 * span)
        duration = random.uniform(1800, 7200)
        w_start = start + timedelta(seconds=offset)
        w_end = min(w_start + timedelta(seconds=duration), end)
        windows.append((w_start, w_end, random.uniform(0.3, 0.9)))
    return windows

def in_anomaly(ts, windows):
    for ws, we, sev in windows:
        if ws <= ts <= we:
            return sev
    return 0.0

def gen_value(tag, ts, start_ts, anomaly, rng):
    _, name, base, amp, pattern, noise = tag
    elapsed = (ts - start_ts).total_seconds()
    hour = ts.hour + ts.minute / 60.0
    if pattern == "sin":
        daily = math.sin(2 * math.pi * hour / 24)
        drift = math.sin(2 * math.pi * elapsed / (86400 * 3))
        val = base + amp * (0.7 * daily + 0.3 * drift)
    elif pattern == "walk":
        seed = int(elapsed / BACKFILL_INTERVAL_SEC)
        val = base + amp * random.Random(seed + hash(name)).gauss(0, 0.3)
    else:
        val = base
    val += rng.gauss(0, noise)
    if anomaly > 0:
        if "Temp" in name or "Alarm" in name:
            val += anomaly * amp * 0.8
        elif "Efficiency" in name or "SoH" in name or "SoC" in name:
            val -= anomaly * amp * 0.6
        else:
            val += anomaly * rng.gauss(0, amp * 0.3)
    return round(val, 4)

def ts_to_micros(dt):
    """Convert datetime to microseconds since epoch (matches Zerobus event_time)."""
    return int(dt.timestamp() * 1_000_000)

# COMMAND ----------

# Generate all rows matching raw_tags Zerobus protobuf schema

import time as _time

t0 = _time.monotonic()
all_rows = []

for site in SITES:
    anomaly_windows = gen_anomaly_windows(start, end)
    print(f"Site: {site['name']} — {len(anomaly_windows)} anomaly windows")

    assets = []
    for u in range(1, 5):
        assets.append((f"BESS{u:02d}", "agl_bess", BESS_TAGS))
        assets.append((f"T{u:02d}", "agl_wind", WIND_TAGS))

    for asset_code, provider, tags in assets:
        rng = random.Random(hash(f"{site['name']}_{asset_code}"))
        ts = start
        while ts < end:
            anomaly = in_anomaly(ts, anomaly_windows)
            quality_str = "Good"
            quality_code = 192
            if anomaly > 0.5 and rng.random() < 0.1:
                quality_str = "Bad"
                quality_code = 0

            event_micros = ts_to_micros(ts)
            ingest_micros = ts_to_micros(ts + timedelta(seconds=rng.uniform(0.1, 2.0)))

            for tag in tags:
                subsystem, signal = tag[0], tag[1]
                val = gen_value(tag, ts, start, anomaly, rng)

                # Build full Ignition-style tag path
                tag_path = f"[{provider}]AGL/Australia/{site['state']}/{site['name']}/Site01/{asset_code}/{subsystem}/{signal}"

                all_rows.append((
                    str(uuid.uuid4()),       # event_id
                    event_micros,            # event_time (bigint micros)
                    tag_path,                # tag_path
                    provider,                # tag_provider
                    val,                     # numeric_value
                    None,                    # string_value
                    None,                    # boolean_value
                    quality_str,             # quality
                    quality_code,            # quality_code
                    "historical_backfill",   # source_system
                    ingest_micros,           # ingestion_timestamp (bigint micros)
                    "Double",                # data_type
                    None,                    # alarm_state
                    0,                       # alarm_priority
                    False,                   # sdt_compressed
                    1.0,                     # compression_ratio
                    False,                   # sdt_enabled
                    0,                       # batch_bytes_sent
                ))
            ts += timedelta(seconds=BACKFILL_INTERVAL_SEC)

gen_elapsed = _time.monotonic() - t0
print(f"\nGenerated {len(all_rows):,} rows in {gen_elapsed:.1f}s")

# COMMAND ----------

# Write to Delta table — schema matches raw_tags exactly

from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType, IntegerType, BooleanType

schema = StructType([
    StructField("event_id", StringType(), False),
    StructField("event_time", LongType(), False),
    StructField("tag_path", StringType(), False),
    StructField("tag_provider", StringType(), True),
    StructField("numeric_value", DoubleType(), True),
    StructField("string_value", StringType(), True),
    StructField("boolean_value", BooleanType(), True),
    StructField("quality", StringType(), True),
    StructField("quality_code", IntegerType(), True),
    StructField("source_system", StringType(), True),
    StructField("ingestion_timestamp", LongType(), True),
    StructField("data_type", StringType(), True),
    StructField("alarm_state", StringType(), True),
    StructField("alarm_priority", IntegerType(), True),
    StructField("sdt_compressed", BooleanType(), True),
    StructField("compression_ratio", DoubleType(), True),
    StructField("sdt_enabled", BooleanType(), True),
    StructField("batch_bytes_sent", LongType(), True),
])

df = spark.createDataFrame(all_rows, schema=schema)
print(f"Writing {df.count():,} rows to {TABLE}...")
df.write.mode("append").saveAsTable(TABLE)
print("Done!")

# COMMAND ----------

# Verify
display(spark.sql(f"""
  SELECT COUNT(*) as row_count,
         COUNT(DISTINCT tag_path) as distinct_tags,
         MIN(from_unixtime(event_time / 1000000)) as earliest,
         MAX(from_unixtime(event_time / 1000000)) as latest
  FROM {TABLE}
  WHERE source_system = 'historical_backfill'
"""))
