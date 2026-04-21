"""BOM Weather Demo — Databricks 101 bolt-on.

Fetches LIVE Bureau of Meteorology observations from Victorian weather stations
directly from the BOM JSON API on each pipeline refresh, then processes through
Bronze → Silver → Gold with DLT expectations at each layer.

Stations: Melbourne Airport, Avalon, Olympic Park, Moorabbin Airport.

Three expectation modes are demonstrated:
  - EXPECT (warn)        — log the violation, keep the row
  - EXPECT ... DROP ROW  — silently remove bad rows
  - EXPECT ... FAIL      — halt the pipeline on violation
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

# Victorian BOM stations: (WMO ID, product code)
_BOM_STATIONS = {
    "94866": "IDV60901",  # Melbourne Airport
    "94854": "IDV60901",  # Avalon Airport
    "95936": "IDV60901",  # Melbourne Olympic Park
    "94870": "IDV60901",  # Moorabbin Airport
}

_ROW_SCHEMA = StructType(
    [
        StructField("station_name", StringType(), True),
        StructField("station_wmo", IntegerType(), True),
        StructField("observation_time_utc", StringType(), True),
        StructField("observation_time_local", StringType(), True),
        StructField("latitude", DoubleType(), True),
        StructField("longitude", DoubleType(), True),
        StructField("air_temp_c", DoubleType(), True),
        StructField("apparent_temp_c", DoubleType(), True),
        StructField("dewpoint_c", DoubleType(), True),
        StructField("relative_humidity_pct", IntegerType(), True),
        StructField("pressure_hpa", DoubleType(), True),
        StructField("wind_direction", StringType(), True),
        StructField("wind_speed_kmh", IntegerType(), True),
        StructField("wind_gust_kmh", IntegerType(), True),
        StructField("rainfall_mm", DoubleType(), True),
        StructField("cloud", StringType(), True),
    ]
)


def _fetch_bom_observations() -> list[dict]:
    """Fetch live observations from BOM JSON API for all configured stations."""
    import json
    import urllib.request

    rows = []
    for wmo, product in _BOM_STATIONS.items():
        url = f"https://www.bom.gov.au/fwo/{product}/{product}.{wmo}.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Databricks-DLT/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for obs in data["observations"]["data"]:
                rain_raw = obs.get("rain_trace", "0")
                try:
                    rain_val = float(rain_raw) if rain_raw and rain_raw != "-" else None
                except (ValueError, TypeError):
                    rain_val = None
                rows.append(
                    {
                        "station_name": obs.get("name"),
                        "station_wmo": int(wmo),
                        "observation_time_utc": obs.get("aifstime_utc"),
                        "observation_time_local": obs.get("local_date_time_full"),
                        "latitude": obs.get("lat"),
                        "longitude": obs.get("lon"),
                        "air_temp_c": obs.get("air_temp"),
                        "apparent_temp_c": obs.get("apparent_t"),
                        "dewpoint_c": obs.get("dewpt"),
                        "relative_humidity_pct": obs.get("rel_hum"),
                        "pressure_hpa": obs.get("press"),
                        "wind_direction": obs.get("wind_dir"),
                        "wind_speed_kmh": obs.get("wind_spd_kmh"),
                        "wind_gust_kmh": obs.get("gust_kmh"),
                        "rainfall_mm": rain_val,
                        "cloud": obs.get("cloud"),
                    }
                )
        except Exception as e:
            # Log but don't fail — other stations may succeed
            print(f"WARN: BOM fetch failed for station {wmo}: {e}")
    return rows


# ═══════════════════════════════════════════════════════════════════════════
# BRONZE — raw ingestion, minimal transform
# ═══════════════════════════════════════════════════════════════════════════


@dp.table(
    name="bom_raw_observations",
    comment="Bronze: live BOM weather observations fetched from Bureau of Meteorology API. "
    "Stations: Melbourne Airport, Avalon, Olympic Park, Moorabbin.",
)
@dp.expect(
    "has_station",
    "station_name IS NOT NULL AND length(trim(station_name)) > 0",
)
@dp.expect(
    "has_observation_time",
    "observation_timestamp IS NOT NULL",
)
def bom_raw_observations():
    """Bronze table: fetch live from BOM JSON API, parse into DataFrame."""
    rows = _fetch_bom_observations()
    return (
        spark.createDataFrame(rows, schema=_ROW_SCHEMA)  # noqa: F821
        .withColumn(
            "observation_timestamp",
            F.to_timestamp(F.col("observation_time_utc"), "yyyyMMddHHmmss"),
        )
        .withColumn("ingested_at", F.current_timestamp())
    )


# ═══════════════════════════════════════════════════════════════════════════
# SILVER — validated, cleaned (expectations DROP bad rows)
# ═══════════════════════════════════════════════════════════════════════════


@dp.table(
    name="bom_validated_observations",
    comment="Silver: BOM observations with quality checks applied. "
    "Invalid rows are dropped by DLT expectations.",
    cluster_by=["observation_timestamp", "station_name"],
)
# --- Completeness checks (warn only — observe the issue) ---
@dp.expect(
    "has_temperature",
    "air_temp_c IS NOT NULL",
)
@dp.expect(
    "has_pressure",
    "pressure_hpa IS NOT NULL",
)
# --- Validity checks (drop bad rows — clean the data) ---
@dp.expect_or_drop(
    "valid_temperature_range",
    "air_temp_c BETWEEN -10 AND 55",
)
@dp.expect_or_drop(
    "valid_humidity",
    "relative_humidity_pct BETWEEN 0 AND 100",
)
@dp.expect_or_drop(
    "not_future_observation",
    "observation_timestamp <= current_timestamp()",
)
# --- Hard contract (fail pipeline if violated) ---
@dp.expect_or_fail(
    "has_station_identity",
    "station_wmo IS NOT NULL",
)
def bom_validated_observations():
    """Silver table: read from bronze, apply quality rules.

    Demonstrates three expectation modes:
      - EXPECT (warn):          has_temperature, has_pressure
      - EXPECT_OR_DROP:         valid_temperature_range, valid_humidity, not_future_observation
      - EXPECT_OR_FAIL:         has_station_identity
    """
    return (
        spark.read.table("bom_raw_observations")  # noqa: F821
        .select(
            "station_name",
            "station_wmo",
            "observation_timestamp",
            "latitude",
            "longitude",
            "air_temp_c",
            "apparent_temp_c",
            "dewpoint_c",
            "relative_humidity_pct",
            "pressure_hpa",
            "wind_direction",
            "wind_speed_kmh",
            "wind_gust_kmh",
            "rainfall_mm",
            "cloud",
            "ingested_at",
        )
    )


# ═══════════════════════════════════════════════════════════════════════════
# GOLD — business-level aggregates
# ═══════════════════════════════════════════════════════════════════════════


@dp.materialized_view(
    name="bom_station_daily_summary",
    comment="Gold: daily weather summary per station. "
    "Min/max/avg temperature, total rainfall, max wind gust.",
)
@dp.expect(
    "valid_avg_temp",
    "avg_temp_c IS NOT NULL",
)
@dp.expect(
    "positive_observation_count",
    "observation_count > 0",
)
def bom_station_daily_summary():
    """Gold materialized view: daily aggregates per weather station."""
    return (
        spark.read.table("bom_validated_observations")  # noqa: F821
        .withColumn("observation_date", F.to_date("observation_timestamp"))
        .groupBy("station_name", "station_wmo", "observation_date")
        .agg(
            F.min("air_temp_c").alias("min_temp_c"),
            F.max("air_temp_c").alias("max_temp_c"),
            F.round(F.avg("air_temp_c"), 1).alias("avg_temp_c"),
            F.round(F.avg("relative_humidity_pct"), 0).alias("avg_humidity_pct"),
            F.round(F.avg("pressure_hpa"), 1).alias("avg_pressure_hpa"),
            F.max("wind_gust_kmh").alias("max_gust_kmh"),
            F.round(F.max("rainfall_mm"), 1).alias("total_rainfall_mm"),
            F.count("*").alias("observation_count"),
        )
    )


@dp.materialized_view(
    name="bom_current_conditions",
    comment="Gold: latest observation per station (live conditions).",
)
@dp.expect(
    "has_station",
    "station_name IS NOT NULL",
)
def bom_current_conditions():
    """Gold materialized view: most recent observation per station."""
    from pyspark.sql.window import Window

    w = Window.partitionBy("station_name").orderBy(F.desc("observation_timestamp"))
    return (
        spark.read.table("bom_validated_observations")  # noqa: F821
        .withColumn("rn", F.row_number().over(w))
        .filter(F.col("rn") == 1)
        .drop("rn")
    )
