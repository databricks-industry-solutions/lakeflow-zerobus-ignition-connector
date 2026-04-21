"""Revenue-at-risk materialized view.

SDP materialized view joining health scores with price forecasts to compute revenue at risk.
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from agl_analytics.config import table

# Demo defaults for AGL Tomago site (MW capacity per asset type)
BESS_CAPACITY_MW = 500.0
SUBSTATION_CAPACITY_MW = 500.0
DEFAULT_CAPACITY_MW = 50.0
HIGH_PRICE_THRESHOLD_AUD_MWH = 300.0


@dp.materialized_view(
    name="revenue_risk",
    comment="Per-asset revenue at risk during high-price windows",
)
@dp.expect("has_asset_id", "asset_id IS NOT NULL AND length(trim(asset_id)) > 0")
@dp.expect("valid_revenue_at_risk", "revenue_at_risk_aud IS NULL OR revenue_at_risk_aud >= 0")
def revenue_risk():
    """Materialized view: revenue at risk per asset.

    Joins health_scores + price_forecast + assets to compute:
    - revenue_at_risk = capacity * hours * price * trip_probability
    - recommended_action based on health score thresholds
    """
    health = spark.read.table(table("health_scores"))  # noqa: F821
    forecast = spark.read.table(table("price_forecast"))  # noqa: F821
    assets = spark.read.table(table("silver_asset_registry"))  # noqa: F821

    # Derive capacity from asset_type (demo defaults for AGL Tomago)
    assets_with_capacity = assets.filter(F.col("active") == True).withColumn(  # noqa: E712
        "capacity_mw",
        F.when(F.col("asset_type") == "BESS", F.lit(BESS_CAPACITY_MW))
        .when(F.col("asset_type") == "SUBSTATION", F.lit(SUBSTATION_CAPACITY_MW))
        .otherwise(F.lit(DEFAULT_CAPACITY_MW)),
    )

    # Find high-price windows
    high_price = forecast.filter(F.col("forecast_price_aud_mwh") > HIGH_PRICE_THRESHOLD_AUD_MWH)

    # Aggregate into a single risk window per region
    windows = high_price.groupBy("region").agg(
        F.min("target_interval").alias("risk_window_start"),
        F.max("target_interval").alias("risk_window_end"),
        F.avg("forecast_price_aud_mwh").alias("forecast_price_aud_mwh"),
    )

    # Cross join all assets with all high-price windows (single-region demo)
    asset_windows = assets_with_capacity.crossJoin(windows)

    # Join with health scores
    with_health = asset_windows.join(health, on="asset_id", how="left")

    # Compute revenue at risk
    # trip_probability = 1 - health_score
    # revenue_at_risk = capacity_mw * window_hours * price * trip_probability
    result = (
        with_health.withColumn("trip_probability", 1.0 - F.coalesce(F.col("health_score"), F.lit(0.5)))
        .withColumn(
            "window_hours",
            (F.unix_timestamp("risk_window_end") - F.unix_timestamp("risk_window_start")) / 3600.0,
        )
        .withColumn(
            "revenue_at_risk_aud",
            F.col("capacity_mw") * F.col("window_hours") * F.col("forecast_price_aud_mwh") * F.col("trip_probability"),
        )
    )

    # Recommended action: deterministic template (runtime-safe for all environments)
    template_action = (
        F.when(F.col("health_score") > 0.8, F.lit("Monitor - no action needed"))
        .when(F.col("health_score") > 0.5, F.concat(F.lit("Schedule inspection before "), F.col("risk_window_start")))
        .when(F.col("health_score") > 0.3, F.lit("Urgent: schedule maintenance tonight"))
        .otherwise(F.lit("Critical: consider preemptive shutdown and repair to protect fleet"))
    )
    result = result.withColumn(
        "recommended_action",
        template_action,
    )

    return result.select(
        F.current_timestamp().alias("computed_at"),
        "asset_id",
        "risk_window_start",
        "risk_window_end",
        "forecast_price_aud_mwh",
        "capacity_mw",
        "health_score",
        "trip_probability",
        "revenue_at_risk_aud",
        "recommended_action",
    )
