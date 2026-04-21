"""
Medallion Architecture Workshop — Simplified DLT Pipeline
==========================================================

This is a teaching-friendly version of the full OT pipeline,
stripped down to the 6 core tables that tell the medallion story.

Pipeline target: medallion catalog (configured in databricks.yml)

Layer flow:
  BRONZE: raw_tags (source) → raw_tags_cleaned (dedup)
  SILVER: parsed_tags → aggregated_tags → enriched_tags
  GOLD:   health_scores → revenue_risk
"""

from __future__ import annotations

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# In production, these come from pipeline settings or environment variables.
# For the workshop, they're hardcoded for clarity.

SOURCE_TABLE = "medallion.bronze.raw_tags"

# Key signals used for health scoring (z-score anomaly detection)
KEY_SIGNALS = [
    "soc_pct", "soh_pct", "rack_temp_c",
    "active_power_mw", "frequency_hz", "voltage_kv", "net_mw",
]


# ===========================================================================
# BRONZE → SILVER: Parse raw tag events
# ===========================================================================

@dp.table(
    name="parsed_tags",
    comment="Silver: raw tags parsed into asset_id, tag_name, and proper timestamps.",
    cluster_by=["event_timestamp", "asset_id"],
)
@dp.expect("valid_event_timestamp", "event_timestamp IS NOT NULL")
@dp.expect("has_asset_id", "asset_id IS NOT NULL AND length(trim(asset_id)) > 0")
@dp.expect("valid_quality_code", "quality_code BETWEEN 0 AND 255")
@dp.expect_or_drop("not_future_event", "event_timestamp <= current_timestamp() + INTERVAL 5 MINUTES")
def parsed_tags():
    """
    Parse the packed tag_path into meaningful business columns.

    Before: tag_path = "[agl_bess]AGL/AU/NSW/Tomago/Site01/bess_01/thermal/rack_temp_c"
    After:  asset_id = "tomago_bess_01", tag_name = "thermal/rack_temp_c"
    """
    return (
        spark.readStream.option("readChangeFeed", "true")
        .table(SOURCE_TABLE)
        # Convert microsecond BIGINT → human-readable TIMESTAMP
        .withColumn("event_timestamp", F.to_timestamp(F.col("event_time") / 1_000_000))
        .withColumn("ingest_timestamp", F.to_timestamp(F.col("ingestion_timestamp") / 1_000_000))
        # Extract location and asset from tag_path
        .withColumn("_location", F.regexp_extract("tag_path", r"/([^/]+)/Site\d+/", 1))
        .withColumn("_asset", F.regexp_extract("tag_path", r"/Site\d+/([^/]+)/", 1))
        .withColumn("asset_id", F.lower(F.concat(F.col("_location"), F.lit("_"), F.col("_asset"))))
        # Map provider → asset_type
        .withColumn(
            "asset_type",
            F.when(F.col("tag_provider") == "agl_bess", "battery_bess")
            .when(F.col("tag_provider") == "agl_grid", "grid_infrastructure")
            .when(F.col("tag_provider") == "agl_market", "market_data")
            .when(F.col("tag_provider") == "agl_cmms", "maintenance")
            .otherwise(F.col("tag_provider")),
        )
        # Extract signal path (everything after Site01/asset/)
        .withColumn("tag_name", F.regexp_extract("tag_path", r"/Site\d+/[^/]+/(.+)$", 1))
        .withColumn("tag_value", F.col("numeric_value"))
        .withColumn("tag_value_str", F.col("string_value"))
        .select(
            "event_timestamp", "ingest_timestamp",
            "asset_id", "asset_type", "tag_name",
            "tag_value", "tag_value_str",
            "quality", "quality_code", "source_system",
        )
    )


# ===========================================================================
# SILVER: 1-minute windowed aggregation
# ===========================================================================

@dp.table(
    name="aggregated_tags",
    comment="Silver: 1-minute tumbling window aggregations per asset per signal.",
    cluster_by=["window_start", "asset_id"],
)
@dp.expect("valid_window", "window_start IS NOT NULL AND window_end IS NOT NULL")
@dp.expect("has_tag_name", "tag_name IS NOT NULL AND length(trim(tag_name)) > 0")
@dp.expect("valid_sample_count", "sample_count > 0")
def aggregated_tags():
    """
    Reduce raw event volume by ~99%.

    Before: 2,700 events/sec × 60 = 162,000 rows/minute
    After:  ~1,350 rows/minute (one per tag per minute)
    """
    return (
        spark.readStream.table("parsed_tags")
        .filter(F.col("tag_value").isNotNull())
        .groupBy(
            F.window("event_timestamp", "1 minute"),
            "asset_id",
            "tag_name",
        )
        .agg(
            F.avg("tag_value").alias("avg_value"),
            F.min("tag_value").alias("min_value"),
            F.max("tag_value").alias("max_value"),
            F.stddev("tag_value").alias("stddev_value"),
            F.count("*").alias("sample_count"),
        )
        .select(
            F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            "asset_id",
            "tag_name",
            "avg_value", "min_value", "max_value",
            "stddev_value", "sample_count",
        )
    )


# ===========================================================================
# SILVER: Enrich with signal metadata
# ===========================================================================

@dp.table(
    name="enriched_tags",
    comment="Silver: aggregated tags enriched with human-readable signal names and units.",
    cluster_by=["window_start", "asset_id"],
)
@dp.expect("valid_window_start", "window_start IS NOT NULL")
@dp.expect("valid_sample_count", "sample_count >= 0")
def enriched_tags():
    """
    Add human-readable context to each signal.

    Before: tag_name = "thermal/rack_temp_c"
    After:  signal_name = "Rack Temperature", unit = "°C", domain = "battery_thermal"
    """
    # In production, this join uses a reference table (silver_signal_mapping).
    # For the workshop, we derive signal_name and unit from tag_name patterns.
    return (
        spark.readStream.table("aggregated_tags")
        .withColumn(
            "signal_name",
            F.when(F.col("tag_name").like("%/soc_pct"), "State of Charge")
            .when(F.col("tag_name").like("%/soh_pct"), "State of Health")
            .when(F.col("tag_name").like("%/rack_temp_c"), "Rack Temperature")
            .when(F.col("tag_name").like("%/ambient_temp_c"), "Ambient Temperature")
            .when(F.col("tag_name").like("%/active_power_mw"), "Active Power")
            .when(F.col("tag_name").like("%/net_mw"), "Net Power (POI)")
            .when(F.col("tag_name").like("%/frequency_hz"), "Grid Frequency")
            .when(F.col("tag_name").like("%/voltage_kv"), "Voltage")
            .when(F.col("tag_name").like("%/rrp_aud_mwh"), "Spot Price (RRP)")
            .otherwise(F.regexp_extract("tag_name", r"[^/]+$", 0)),
        )
        .withColumn(
            "unit",
            F.when(F.col("tag_name").like("%_pct"), "%")
            .when(F.col("tag_name").like("%_temp_c"), "°C")
            .when(F.col("tag_name").like("%_mw"), "MW")
            .when(F.col("tag_name").like("%_hz"), "Hz")
            .when(F.col("tag_name").like("%_kv"), "kV")
            .when(F.col("tag_name").like("%_aud%"), "AUD/MWh"),
        )
        .withColumn(
            "source_domain",
            F.when(F.col("tag_name").like("thermal/%"), "battery_thermal")
            .when(F.col("tag_name").like("power/%"), "battery_power")
            .when(F.col("tag_name").like("poi/%"), "grid_power")
            .when(F.col("tag_name").like("dispatch/%"), "grid_dispatch")
            .when(F.col("tag_name").like("market/%"), "market_data")
            .otherwise("other"),
        )
    )


# ===========================================================================
# GOLD: Health scores per asset (materialized view)
# ===========================================================================

@dp.materialized_view(
    name="health_scores",
    comment="Gold: per-asset health score (0=critical, 1=healthy) via z-score anomaly detection.",
)
@dp.expect("valid_health_score", "health_score IS NULL OR (health_score >= 0 AND health_score <= 1)")
@dp.expect("has_asset_id", "asset_id IS NOT NULL AND length(trim(asset_id)) > 0")
def health_scores():
    """
    One row per asset. One number (0-1). The operations team's morning dashboard.

    Algorithm: z-score anomaly detection on key signals.
    If a signal deviates > 2 std devs from its rolling mean, it's flagged.
    health_score = 1 - (anomalous_signals / total_key_signals)
    """
    enriched = spark.read.table("enriched_tags")

    # Filter to key signals and last 1 hour
    key_signals_pattern = "|".join(KEY_SIGNALS)
    recent = (
        enriched
        .filter(F.col("window_start") > F.current_timestamp() - F.expr("INTERVAL 1 HOUR"))
        .filter(F.col("tag_name").rlike(key_signals_pattern))
        .filter(F.col("avg_value").isNotNull())
    )

    # Compute rolling mean and stddev per asset per signal
    stats = (
        recent
        .groupBy("asset_id", "tag_name")
        .agg(
            F.avg("avg_value").alias("mean_val"),
            F.stddev("avg_value").alias("stddev_val"),
            F.count("*").alias("window_count"),
            F.last("avg_value").alias("latest_value"),
        )
        .filter(F.col("window_count") >= 5)  # need enough data
    )

    # Z-score anomaly detection
    anomalies = (
        stats
        .withColumn(
            "zscore",
            F.when(
                F.col("stddev_val") > 0,
                F.abs(F.col("latest_value") - F.col("mean_val")) / F.col("stddev_val"),
            ).otherwise(0.0),
        )
        .withColumn("is_anomalous", F.col("zscore") > 2.0)
    )

    # Score per asset
    return (
        anomalies
        .groupBy("asset_id")
        .agg(
            F.count("*").alias("total_key_tags"),
            F.sum(F.when(F.col("is_anomalous"), 1).otherwise(0)).alias("anomaly_count"),
            F.max(F.when(F.col("is_anomalous"), F.col("tag_name"))).alias("primary_risk_tag"),
            F.max(F.when(F.col("is_anomalous"), F.col("zscore"))).alias("max_zscore"),
        )
        .withColumn(
            "health_score",
            F.round(1.0 - (F.col("anomaly_count") / F.col("total_key_tags")), 2),
        )
        .withColumn("scored_at", F.current_timestamp())
        .withColumn(
            "risk_description",
            F.when(F.col("anomaly_count") == 0, "All signals within normal range")
            .when(F.col("anomaly_count") == 1, F.concat(
                F.lit("1 signal anomalous: "), F.coalesce(F.col("primary_risk_tag"), F.lit("unknown")),
            ))
            .otherwise(F.concat(
                F.col("anomaly_count"), F.lit(" signals anomalous"),
            )),
        )
        .withColumn(
            "estimated_hours_to_failure",
            F.round(720.0 * F.pow(F.col("health_score"), 2), 0),
        )
        .select(
            "scored_at", "asset_id", "health_score",
            "primary_risk_tag", "risk_description",
            "anomaly_count", "total_key_tags",
            "estimated_hours_to_failure",
        )
    )


# ===========================================================================
# GOLD: Revenue at risk (materialized view)
# ===========================================================================

@dp.materialized_view(
    name="revenue_risk",
    comment="Gold: revenue at risk per asset during high-price windows.",
)
@dp.expect("has_asset_id", "asset_id IS NOT NULL AND length(trim(asset_id)) > 0")
@dp.expect("valid_revenue", "revenue_at_risk_aud IS NULL OR revenue_at_risk_aud >= 0")
def revenue_risk():
    """
    The business question: "How much money do we lose if an unhealthy asset trips
    during the next high-price window?"

    health_score × price_forecast × capacity = dollars_at_risk
    """
    health = spark.read.table("health_scores").filter(F.col("health_score") < 1.0)

    return (
        health
        .withColumn(
            "capacity_mw",
            F.when(F.col("asset_id").like("%bess%"), 500.0).otherwise(50.0),
        )
        .withColumn("forecast_price_aud_mwh", F.lit(350.0))  # Simulated high-price window
        .withColumn("risk_window_hours", F.lit(4.0))
        .withColumn("trip_probability", F.round(1.0 - F.col("health_score"), 2))
        .withColumn(
            "revenue_at_risk_aud",
            F.round(
                F.col("capacity_mw") * F.col("risk_window_hours")
                * F.col("forecast_price_aud_mwh") * (1.0 - F.col("health_score")),
                2,
            ),
        )
        .withColumn(
            "recommended_action",
            F.when(F.col("health_score") >= 0.9, "No action required")
            .when(F.col("health_score") >= 0.7, "Monitor — schedule inspection")
            .when(F.col("health_score") >= 0.5, "Inspect before next high-price window")
            .otherwise("Immediate inspection required — consider curtailment"),
        )
        .withColumn("computed_at", F.current_timestamp())
        .select(
            "computed_at", "asset_id", "health_score", "trip_probability",
            "capacity_mw", "forecast_price_aud_mwh", "risk_window_hours",
            "revenue_at_risk_aud", "recommended_action",
        )
    )
