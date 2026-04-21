#!/usr/bin/env python3
"""Generate and insert synthetic historical tag events into raw_tags.

Creates realistic OT telemetry spanning BACKFILL_DAYS (default 7) so that
the demo app's time-travel, fleet snapshot, and forensics features have
data to show regardless of when the simulator was last running.

Generates data for all 5 sites × 4 BESS units + 4 wind turbines per site
at 5-minute intervals (configurable via BACKFILL_INTERVAL_SEC).

Includes 2-3 anomaly windows per site to make health scores interesting.

Two execution modes:
  spark   — Serverless Spark Connect (fast, ~2 min for 1.2M rows)
  sql     — SQL warehouse Statement Execution API (slower, ~8 min)

Usage:
  # Spark Connect (default, fast)
  DATABRICKS_CONFIG_PROFILE=daveok uv run --with 'databricks-connect' \
    python onboarding/databricks/backfill_historical_data.py

  # SQL warehouse fallback
  BACKFILL_MODE=sql DATABRICKS_CONFIG_PROFILE=daveok uv run --with databricks-sdk \
    python onboarding/databricks/backfill_historical_data.py

Optional env:
  BACKFILL_DAYS          Number of days to backfill (default: 7)
  BACKFILL_INTERVAL_SEC  Seconds between events per tag (default: 300)
  BACKFILL_MODE          'spark' (default) or 'sql'
  CATALOG                Unity Catalog catalog (default: agl_demo)
  SCHEMA                 Unity Catalog schema (default: ot)
  DATABRICKS_WAREHOUSE_ID  SQL warehouse (only for sql mode)
  DRY_RUN                Set to 1 to print stats without inserting
"""

from __future__ import annotations

import math
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

# ── Config ────────────────────────────────────────────────────────────────

BACKFILL_DAYS = int(os.environ.get("BACKFILL_DAYS", "7"))
BACKFILL_INTERVAL_SEC = int(os.environ.get("BACKFILL_INTERVAL_SEC", "300"))
BACKFILL_MODE = os.environ.get("BACKFILL_MODE", "spark").lower()
CATALOG = os.environ.get("CATALOG", os.environ.get("APP_TARGET_CATALOG", "agl_demo"))
SCHEMA = os.environ.get("SCHEMA", os.environ.get("APP_TARGET_SCHEMA", "ot"))
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "e4082fdb7ea19a15")
DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
SQL_BATCH_SIZE = 5000  # rows per INSERT statement (sql mode only)

# ── Sites & Assets ────────────────────────────────────────────────────────

SITES = [
    {"name": "tomago", "region": "NSW"},
    {"name": "liddell", "region": "NSW"},
    {"name": "broken_hill", "region": "NSW"},
    {"name": "callide", "region": "QLD"},
    {"name": "gladstone", "region": "QLD"},
]

# ── Tag Profiles ──────────────────────────────────────────────────────────
# (tag_name, base, amplitude, pattern, noise)

BESS_TAGS: list[tuple[str, float, float, str, float]] = [
    ("battery/soc_pct", 50.0, 40.0, "sin", 2.0),
    ("battery/soh_pct", 95.0, 3.0, "sin", 0.5),
    ("battery/voltage_v", 400.0, 15.0, "sin", 1.0),
    ("battery/current_a", 0.0, 300.0, "sin", 10.0),
    ("battery/temperature_c", 28.0, 8.0, "sin", 1.0),
    ("battery/charge_rate_percent", 50.0, 45.0, "sin", 3.0),
    ("battery/discharge_rate_percent", 50.0, 45.0, "sin", 3.0),
    ("inverter/power_kw", 250.0, 200.0, "sin", 15.0),
    ("inverter/frequency_hz", 50.0, 0.3, "sin", 0.02),
    ("inverter/efficiency_percent", 95.0, 3.0, "sin", 0.5),
    ("thermal/coolant_temp_c", 25.0, 6.0, "sin", 0.5),
    ("thermal/ambient_temp_c", 22.0, 10.0, "sin", 1.0),
    ("status/operational_state", 1.0, 0.0, "const", 0.0),
    ("status/alarm_code", 0.0, 0.0, "const", 0.0),
    ("status/mode", 1.0, 0.0, "const", 0.0),
    ("status/cooling_active", 1.0, 0.0, "const", 0.0),
]

WIND_TAGS: list[tuple[str, float, float, str, float]] = [
    ("generator/speed_rpm", 900.0, 600.0, "sin", 30.0),
    ("generator/power_kw", 2500.0, 2000.0, "sin", 100.0),
    ("generator/torque_nm", 25000.0, 15000.0, "sin", 500.0),
    ("rotor/blade_pitch_deg", 12.0, 10.0, "walk", 1.0),
    ("rotor/wind_speed_ms", 12.0, 8.0, "sin", 1.5),
    ("rotor/rotor_rpm", 10.0, 6.0, "sin", 0.5),
    ("nacelle/yaw_angle_deg", 180.0, 90.0, "walk", 5.0),
    ("nacelle/temperature_c", 35.0, 15.0, "sin", 1.0),
    ("grid/voltage_v", 400.0, 15.0, "sin", 1.0),
    ("grid/frequency_hz", 50.0, 0.3, "sin", 0.02),
    ("grid/reactive_power_kvar", 0.0, 500.0, "sin", 30.0),
    ("status/operational_state", 1.0, 0.0, "const", 0.0),
    ("status/alarm_code", 0.0, 0.0, "const", 0.0),
    ("turbine/mode", 1.0, 0.0, "const", 0.0),
    ("grid/fault_detected", 0.0, 0.0, "const", 0.0),
]

# ── Anomaly Windows ───────────────────────────────────────────────────────


def _generate_anomaly_windows(
    start: datetime, end: datetime, count: int = 3
) -> list[tuple[datetime, datetime, float]]:
    """Random anomaly windows. Returns (start, end, severity 0-1) tuples."""
    span = (end - start).total_seconds()
    windows = []
    for _ in range(count):
        offset = random.uniform(0.1 * span, 0.9 * span)
        duration = random.uniform(1800, 7200)  # 30 min to 2 hours
        w_start = start + timedelta(seconds=offset)
        w_end = w_start + timedelta(seconds=duration)
        severity = random.uniform(0.3, 0.9)
        windows.append((w_start, min(w_end, end), severity))
    return windows


def _in_anomaly(
    ts: datetime, windows: list[tuple[datetime, datetime, float]]
) -> float:
    for w_start, w_end, severity in windows:
        if w_start <= ts <= w_end:
            return severity
    return 0.0


# ── Value Generation ──────────────────────────────────────────────────────


def _generate_value(
    tag: tuple[str, float, float, str, float],
    ts: datetime,
    start: datetime,
    anomaly_severity: float,
    rng: random.Random,
) -> float:
    _name, base, amplitude, pattern, noise = tag
    elapsed = (ts - start).total_seconds()
    hour_of_day = ts.hour + ts.minute / 60.0

    if pattern == "sin":
        daily = math.sin(2 * math.pi * hour_of_day / 24)
        drift = math.sin(2 * math.pi * elapsed / (86400 * 3))
        val = base + amplitude * (0.7 * daily + 0.3 * drift)
    elif pattern == "walk":
        seed = int(elapsed / BACKFILL_INTERVAL_SEC)
        walk_rng = random.Random(seed + hash(_name))
        val = base + amplitude * (walk_rng.gauss(0, 0.3))
    else:
        val = base

    val += rng.gauss(0, noise)

    if anomaly_severity > 0:
        if "temp" in _name or "alarm" in _name:
            val += anomaly_severity * amplitude * 0.8
        elif "efficiency" in _name or "soh" in _name or "soc" in _name:
            val -= anomaly_severity * amplitude * 0.6
        else:
            val += anomaly_severity * rng.gauss(0, amplitude * 0.3)

    return round(val, 4)


# ── Row Generation (dict-based, mode-agnostic) ───────────────────────────


def _generate_asset_rows(
    asset_id: str,
    asset_type: str,
    tags: list[tuple[str, float, float, str, float]],
    start: datetime,
    end: datetime,
    anomaly_windows: list[tuple[datetime, datetime, float]],
) -> list[dict]:
    """Generate rows as dicts for one asset over the full time range."""
    rows: list[dict] = []
    rng = random.Random(hash(asset_id))
    ts = start

    while ts < end:
        anomaly = _in_anomaly(ts, anomaly_windows)
        quality = 192
        if anomaly > 0.5 and rng.random() < 0.1:
            quality = 0

        ingest_ts = ts + timedelta(seconds=rng.uniform(0.1, 2.0))

        for tag in tags:
            val = _generate_value(tag, ts, start, anomaly, rng)
            rows.append({
                "event_timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "ingest_timestamp": ingest_ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "asset_id": asset_id,
                "asset_type": asset_type,
                "tag_name": tag[0],
                "tag_value": val,
                "quality": quality,
                "source_system": "historical_backfill",
                "sdt_compressed": False,
                "compression_ratio": 1.0,
            })

        ts += timedelta(seconds=BACKFILL_INTERVAL_SEC)

    return rows


# ── Spark Connect Writer ─────────────────────────────────────────────────


def _write_spark(all_rows: list[dict], table: str) -> None:
    """Write rows via Serverless Spark Connect — fast bulk append."""
    from databricks.connect import DatabricksSession
    from pyspark.sql.types import (
        BooleanType,
        DoubleType,
        IntegerType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    print("  Connecting to Serverless Spark Connect...")
    spark = DatabricksSession.builder.profile(
        os.environ.get("DATABRICKS_CONFIG_PROFILE", "daveok")
    ).getOrCreate()

    schema = StructType([
        StructField("event_timestamp", StringType(), False),
        StructField("ingest_timestamp", StringType(), False),
        StructField("asset_id", StringType(), False),
        StructField("asset_type", StringType(), False),
        StructField("tag_name", StringType(), False),
        StructField("tag_value", DoubleType(), False),
        StructField("quality", IntegerType(), False),
        StructField("source_system", StringType(), False),
        StructField("sdt_compressed", BooleanType(), False),
        StructField("compression_ratio", DoubleType(), True),
    ])

    print(f"  Creating DataFrame with {len(all_rows):,} rows...")
    # Convert to tuples for faster DataFrame creation
    tuples = [
        (
            r["event_timestamp"], r["ingest_timestamp"],
            r["asset_id"], r["asset_type"], r["tag_name"],
            r["tag_value"], r["quality"], r["source_system"],
            r["sdt_compressed"], r["compression_ratio"],
        )
        for r in all_rows
    ]
    df = spark.createDataFrame(tuples, schema=schema)

    # Cast string timestamps to proper TIMESTAMP type before writing
    from pyspark.sql.functions import to_timestamp
    df = df.withColumn("event_timestamp", to_timestamp("event_timestamp")) \
           .withColumn("ingest_timestamp", to_timestamp("ingest_timestamp"))

    print(f"  Writing to {table} (mode=append)...")
    df.write.mode("append").saveAsTable(table)
    print(f"  ✓ Spark write complete")

    spark.stop()


# ── SQL Warehouse Writer ─────────────────────────────────────────────────


def _escape(s: str) -> str:
    return s.replace("'", "''")


def _write_sql(all_rows: list[dict], table: str, total_rows: int) -> None:
    """Write rows via SQL warehouse INSERT VALUES — slower but no Spark dep."""
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import StatementState

    w = WorkspaceClient()
    total_inserted = 0
    t0 = time.monotonic()

    for batch_start in range(0, len(all_rows), SQL_BATCH_SIZE):
        batch = all_rows[batch_start : batch_start + SQL_BATCH_SIZE]
        values = ",\n".join(
            f"('{r['event_timestamp']}', '{r['ingest_timestamp']}', "
            f"'{_escape(r['asset_id'])}', '{_escape(r['asset_type'])}', "
            f"'{_escape(r['tag_name'])}', {r['tag_value']}, "
            f"{r['quality']}, '{r['source_system']}', "
            f"{'true' if r['sdt_compressed'] else 'false'}, {r['compression_ratio']})"
            for r in batch
        )
        sql = (
            f"INSERT INTO {table} "
            "(event_timestamp, ingest_timestamp, asset_id, asset_type, "
            "tag_name, tag_value, quality, source_system, sdt_compressed, compression_ratio) "
            f"VALUES\n{values}"
        )

        try:
            resp = w.statement_execution.execute_statement(
                warehouse_id=WAREHOUSE_ID,
                statement=sql,
                wait_timeout="120s",
            )
            state = resp.status.state if resp.status else None
            ok = state is not None and (
                state == StatementState.SUCCEEDED
                or "SUCCEEDED" in str(state)
            )
            if not ok:
                err = resp.status.error if resp.status else None
                msg = err.message if err else str(resp.status)
                print(f"\n    ✘ Batch failed: {msg[:200]}")
                sys.exit(1)
        except Exception as exc:
            print(f"\n    ✘ Exception: {exc}")
            sys.exit(1)

        total_inserted += len(batch)
        pct = total_inserted / total_rows * 100
        elapsed = time.monotonic() - t0
        rate = total_inserted / elapsed if elapsed > 0 else 0
        sys.stdout.write(
            f"\r    Progress: {total_inserted:,}/{total_rows:,} ({pct:.0f}%) "
            f"| {rate:.0f} rows/s | {elapsed:.0f}s elapsed"
        )
        sys.stdout.flush()

    print()


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = end - timedelta(days=BACKFILL_DAYS)

    intervals = int((end - start).total_seconds() / BACKFILL_INTERVAL_SEC)
    tags_per_site = 4 * len(BESS_TAGS) + 4 * len(WIND_TAGS)
    total_rows = intervals * tags_per_site * len(SITES)

    print("╔══════════════════════════════════════════════╗")
    print("║  Historical Data Backfill                    ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║  Range:     {start.strftime('%Y-%m-%d %H:%M')} → {end.strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"║  Days:      {BACKFILL_DAYS}")
    print(f"║  Interval:  {BACKFILL_INTERVAL_SEC}s")
    print(f"║  Sites:     {len(SITES)}")
    print(f"║  Target:    {CATALOG}.{SCHEMA}.raw_tags")
    print(f"║  Mode:      {BACKFILL_MODE}")
    print(f"║  Rows:      {total_rows:,}")
    print(f"║  Dry run:   {DRY_RUN}")
    print("╚══════════════════════════════════════════════╝")

    if DRY_RUN:
        print("\n  DRY_RUN=1 — skipping insert.")
        return

    table = f"{CATALOG}.{SCHEMA}.raw_tags"
    t0 = time.monotonic()

    # Generate all rows in memory per site, then write
    all_rows: list[dict] = []

    for site in SITES:
        site_name = site["name"]
        anomaly_windows = _generate_anomaly_windows(start, end, count=3)
        print(f"\n▸ Generating: {site_name} ({len(anomaly_windows)} anomaly windows)")
        for aw in anomaly_windows:
            print(f"    Anomaly: {aw[0].strftime('%m-%d %H:%M')} → {aw[1].strftime('%m-%d %H:%M')} (severity {aw[2]:.1f})")

        for unit in range(1, 5):
            asset_id = f"{site_name}_bess{unit:02d}"
            rows = _generate_asset_rows(asset_id, "battery_bess", BESS_TAGS, start, end, anomaly_windows)
            all_rows.extend(rows)
            print(f"    {asset_id}: {len(rows):,} rows")

        for unit in range(1, 5):
            asset_id = f"wind_{site_name}_t{unit:02d}"
            rows = _generate_asset_rows(asset_id, "wind_turbine", WIND_TAGS, start, end, anomaly_windows)
            all_rows.extend(rows)
            print(f"    {asset_id}: {len(rows):,} rows")

    gen_elapsed = time.monotonic() - t0
    print(f"\n  Generated {len(all_rows):,} rows in {gen_elapsed:.1f}s")

    # Write
    print(f"\n▸ Writing via {BACKFILL_MODE}...")
    if BACKFILL_MODE == "spark":
        _write_spark(all_rows, table)
    else:
        _write_sql(all_rows, table, total_rows)

    elapsed = time.monotonic() - t0
    print(f"\n✓ Backfill complete: {len(all_rows):,} rows in {elapsed:.0f}s")
    print(f"  Verify: SELECT COUNT(*), MIN(event_timestamp), MAX(event_timestamp)")
    print(f"          FROM {table} WHERE source_system = 'historical_backfill'")


if __name__ == "__main__":
    main()
