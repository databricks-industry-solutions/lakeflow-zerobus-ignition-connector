"""Data Blend Demo — Databricks 101 showcase.

Demonstrates the Lakehouse superpower: blending OT sensor data, weather
observations, and electricity market prices in a single pipeline.

All three sources land independently (streaming + batch) and are joined
here at the Gold layer on 5-minute time windows.

New tables only — does not modify any existing demo tables.
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


# ═══════════════════════════════════════════════════════════════════════════
# GOLD: OT + Weather + Market blended on 5-min windows
# ═══════════════════════════════════════════════════════════════════════════


@dp.materialized_view(
    name="blended_operational_context",
    comment="Gold: 5-minute operational context blending OT asset telemetry, "
    "BOM weather conditions, and NEM electricity spot prices. "
    "Demonstrates cross-domain data fusion in a single Lakeflow pipeline.",
)
@dp.expect(
    "has_time_window",
    "window_5min IS NOT NULL",
)
@dp.expect(
    "has_asset_data",
    "avg_value IS NOT NULL",
)
def blended_operational_context():
    """Gold view: join OT enriched tags + BOM weather + NEM prices on 5-min windows.

    OT data (1-min aggregated_tags) is rolled up to 5-min buckets, then
    left-joined with BOM weather (nearest observation) and NEM spot prices
    (exact 5-min dispatch interval). This shows how Databricks can unify
    operational, environmental, and market data without ETL middleware.
    """
    from pyspark.sql.window import Window

    # --- OT: aggregate enriched_tags from 1-min to 5-min windows ---
    enriched = spark.read.table("enriched_tags")  # noqa: F821

    ot_5min = (
        enriched
        .withColumn(
            "window_5min",
            F.window("window_start", "5 minutes").start,
        )
        .groupBy("window_5min", "asset_id", "signal_name", "unit")
        .agg(
            F.round(F.avg("avg_value"), 2).alias("avg_value"),
            F.min("min_value").alias("min_value"),
            F.max("max_value").alias("max_value"),
            F.sum("sample_count").alias("sample_count"),
        )
    )

    # --- BOM: nearest observation per 5-min window ---
    bom = spark.read.table("bom_validated_observations")  # noqa: F821

    bom_5min = (
        bom
        .withColumn(
            "window_5min",
            F.window("observation_timestamp", "5 minutes").start,
        )
        .withColumn(
            "rn",
            F.row_number().over(
                Window.partitionBy("window_5min")
                .orderBy(F.desc("observation_timestamp"))
            ),
        )
        .filter(F.col("rn") == 1)
        .select(
            "window_5min",
            F.col("station_name").alias("weather_station"),
            F.col("air_temp_c"),
            F.col("wind_speed_kmh"),
            F.col("relative_humidity_pct"),
            F.col("pressure_hpa"),
        )
    )

    # --- NEM: spot price per 5-min dispatch interval ---
    nem = spark.read.table("nem_dispatch_prices")  # noqa: F821

    # Use VIC1 as the default region (Victorian assets)
    nem_5min = (
        nem
        .filter(F.col("region_id") == "VIC1")
        .withColumn(
            "window_5min",
            F.window("dispatch_timestamp", "5 minutes").start,
        )
        .withColumn(
            "rn",
            F.row_number().over(
                Window.partitionBy("window_5min")
                .orderBy(F.desc("dispatch_timestamp"))
            ),
        )
        .filter(F.col("rn") == 1)
        .select(
            "window_5min",
            F.col("rrp").alias("spot_price_aud_mwh"),
            F.col("region_id").alias("nem_region"),
        )
    )

    # --- JOIN: OT left-join weather left-join market ---
    return (
        ot_5min
        .join(bom_5min, on="window_5min", how="left")
        .join(nem_5min, on="window_5min", how="left")
        .select(
            "window_5min",
            "asset_id",
            "signal_name",
            "unit",
            "avg_value",
            "min_value",
            "max_value",
            "sample_count",
            "weather_station",
            "air_temp_c",
            "wind_speed_kmh",
            "relative_humidity_pct",
            "pressure_hpa",
            "nem_region",
            "spot_price_aud_mwh",
        )
    )
