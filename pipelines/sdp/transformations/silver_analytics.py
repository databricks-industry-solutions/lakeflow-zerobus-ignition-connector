"""Silver to Gold analytics - health_scores and health_score_history MVs.

SDP materialized views that compute per-asset health scores by blending:
  1. Z-score anomaly detection on the live stream (enriched_tags)
  2. IsolationForest ML model (when trained model is available in UC registry)

health_scores: current snapshot (last 1 hour)
health_score_history: hourly buckets over all available data for trend analysis

Blend formula: health_score = 0.6 * zscore_health + 0.4 * ml_health
Falls back to z-score only when the ML model is not registered.
"""

import logging

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from agl_analytics.config import table
from agl_analytics.health import (
    BATTERY_KEY_TAGS,
    FEATURE_COLS,
    SIGNAL_FILL_VALUES,
    WIND_KEY_TAGS,
    load_health_model,
)

log = logging.getLogger(__name__)


@dp.materialized_view(
    name="health_scores",
    comment="Per-asset health scores from z-score anomaly detection on live stream",
)
@dp.expect("valid_health_score", "health_score IS NULL OR (health_score >= 0 AND health_score <= 1)")
@dp.expect("has_asset_id", "asset_id IS NOT NULL AND length(trim(asset_id)) > 0")
def health_scores():
    """Materialized view: health scores per asset.

    Uses z-score anomaly detection on the last hour of enriched_tags.
    Health = 1.0 - (anomalous_key_tags / total_key_tags). Deviations
    from recent behaviour (rolling mean/stddev) are flagged; primary_risk_tag
    is the tag with the largest absolute z-score.
    """
    enriched = spark.read.table(table("enriched_tags"))  # noqa: F821
    assets = spark.read.table(table("silver_asset_registry"))  # noqa: F821

    one_hour_ago = F.current_timestamp() - F.expr("INTERVAL 1 HOUR")
    recent = enriched.filter(F.col("window_start") >= one_hour_ago)

    tag_stats = recent.groupBy("asset_id", "signal_name").agg(
        F.avg("avg_value").alias("rolling_mean"),
        F.stddev("avg_value").alias("rolling_stddev"),
        F.last("avg_value").alias("current_value"),
    )

    # Left join so rows without a registry entry (e.g. simulator) still get scored
    with_assets = tag_stats.join(
        assets.select("asset_id", "asset_type"), on="asset_id", how="left"
    )
    # Infer asset_type from asset_id when registry has no row (e.g. bess_* -> battery_bess, wind_* -> wind_turbine)
    with_assets = with_assets.withColumn(
        "asset_type",
        F.coalesce(
            F.col("asset_type"),
            F.when(F.col("asset_id").rlike("^wind_"), F.lit("wind_turbine"))
            .otherwise(F.lit("battery_bess")),
        ),
    )

    wind_tags = F.array([F.lit(t) for t in WIND_KEY_TAGS])
    battery_tags = F.array([F.lit(t) for t in BATTERY_KEY_TAGS])
    key_tags_col = F.when(
        F.col("asset_type") == "wind_turbine", wind_tags
    ).otherwise(battery_tags)

    key_tag_data = with_assets.filter(
        F.array_contains(key_tags_col, F.col("signal_name"))
    )

    zscore_data = key_tag_data.withColumn(
        "zscore",
        F.when(F.col("rolling_stddev") == 0, F.lit(0.0)).otherwise(
            (F.col("current_value") - F.col("rolling_mean"))
            / F.col("rolling_stddev")
        ),
    ).withColumn("is_anomalous", F.abs(F.col("zscore")) > 2.0)

    zscore_agg = zscore_data.groupBy("asset_id").agg(
        F.sum(F.when(F.col("is_anomalous"), 1).otherwise(0)).alias(
            "anomalous_count"
        ),
        F.count("*").alias("total_key_tags"),
        F.max_by("signal_name", F.abs(F.col("zscore"))).alias(
            "primary_risk_tag"
        ),
        F.max(F.abs(F.col("zscore"))).alias("max_zscore"),
        F.collect_list(
            F.when(F.col("is_anomalous"), F.col("signal_name"))
        ).alias("anomaly_tags_raw"),
    )

    zscore_scores = zscore_agg.withColumn(
        "zscore_health",
        F.when(F.col("total_key_tags") == 0, F.lit(1.0)).otherwise(
            1.0 - F.col("anomalous_count") / F.col("total_key_tags")
        ),
    )

    # -----------------------------------------------------------------
    # ML model scoring (IsolationForest) - optional, with z-score fallback
    # -----------------------------------------------------------------
    model, feature_cols = load_health_model()
    ml_active = model is not None

    if ml_active:
        # Pivot enriched_tags from long to wide: one row per asset, one col per feature
        pivoted = (
            recent.filter(F.col("signal_name").isin(feature_cols))
            .groupBy("asset_id")
            .pivot("signal_name", feature_cols)
            .agg(F.last("avg_value"))
        )

        # Guard: skip ML scoring if too many assets to collect safely
        MAX_ASSETS_FOR_ML = 10_000
        asset_count = pivoted.count()
        if asset_count > MAX_ASSETS_FOR_ML:
            log.warning(
                "Skipping ML scoring: %d assets exceeds limit (%d)",
                asset_count, MAX_ASSETS_FOR_ML,
            )
            ml_active = False

    if ml_active:
        try:
            # Collect to pandas (small - one row per asset), fill missing with midpoints
            pdf = pivoted.toPandas().set_index("asset_id")
            for col in feature_cols:
                if col not in pdf.columns:
                    pdf[col] = SIGNAL_FILL_VALUES[col]
                else:
                    pdf[col] = pdf[col].fillna(SIGNAL_FILL_VALUES[col])
            X = pdf[feature_cols]

            # decision_function: higher = more normal, lower = more anomalous
            raw_scores = model.decision_function(X)

            # Normalize to [0, 1]: 0 = anomalous, 1 = healthy
            import numpy as np

            s_min, s_max = raw_scores.min(), raw_scores.max()
            if s_max - s_min > 0:
                ml_scores = (raw_scores - s_min) / (s_max - s_min)
            else:
                ml_scores = np.ones_like(raw_scores)

            pdf["ml_health"] = ml_scores
            ml_df = spark.createDataFrame(  # noqa: F821
                pdf[["ml_health"]].reset_index().rename(columns={"index": "asset_id"})
            )

            # Join ML scores back
            zscore_scores = zscore_scores.join(ml_df, on="asset_id", how="left")
            log.info("ML model scoring active - blending with z-score")
        except Exception as exc:
            log.warning("ML scoring failed, falling back to z-score: %s", exc)
            ml_active = False

    if not ml_active:
        zscore_scores = zscore_scores.withColumn("ml_health", F.lit(None).cast("double"))
        log.info("ML model not available - using z-score only")

    # -----------------------------------------------------------------
    # Blend scores: 0.6 * zscore + 0.4 * ml (COALESCE to zscore-only fallback)
    # -----------------------------------------------------------------
    blended = zscore_scores.withColumn(
        "health_score",
        F.coalesce(
            F.lit(0.6) * F.col("zscore_health") + F.lit(0.4) * F.col("ml_health"),
            F.col("zscore_health"),
        ),
    )

    # Estimated hours to failure: 720 * score^2 (healthy=720h, critical=0h)
    blended = blended.withColumn(
        "estimated_hours_to_failure",
        F.round(F.lit(720.0) * F.pow(F.col("health_score"), 2), 1),
    )

    # Risk description: deterministic template (runtime-safe for all environments)
    risk_prefix = F.lit("ML+Z: ") if ml_active else F.lit("Z-score: ")
    template_risk_desc = F.concat(
        risk_prefix,
        F.coalesce(F.col("primary_risk_tag"), F.lit("unknown")),
        F.lit(" (z-score: "),
        F.round(F.col("max_zscore"), 1),
        F.lit(")"),
    )

    return blended.select(
        F.current_timestamp().alias("scored_at"),
        "asset_id",
        "health_score",
        "primary_risk_tag",
        template_risk_desc.alias("risk_description"),
        F.filter(F.col("anomaly_tags_raw"), lambda x: x.isNotNull()).alias(
            "anomaly_tags"
        ),
        "estimated_hours_to_failure",
    )


# ---------------------------------------------------------------------------
# Health Score History — hourly z-score health over all available data
# ---------------------------------------------------------------------------


@dp.materialized_view(
    name="health_score_history",
    comment="Hourly health scores per asset for fleet trend analysis",
)
def health_score_history():
    """Materialized view: historical health scores bucketed by hour.

    Same z-score logic as health_scores but computed per hourly window
    across all available enriched_tags data. Enables trend queries like
    "show me fleet health over the last 7 days".
    """
    enriched = spark.read.table(table("enriched_tags"))  # noqa: F821
    assets = spark.read.table(table("silver_asset_registry"))  # noqa: F821

    # Truncate window_start to hour for bucketing
    hourly = enriched.withColumn(
        "hour_bucket", F.date_trunc("hour", F.col("window_start"))
    )

    # Stats per asset, signal, hour
    tag_stats = hourly.groupBy("hour_bucket", "asset_id", "signal_name").agg(
        F.avg("avg_value").alias("rolling_mean"),
        F.stddev("avg_value").alias("rolling_stddev"),
        F.last("avg_value").alias("current_value"),
    )

    # Join asset type
    with_assets = tag_stats.join(
        assets.select("asset_id", "asset_type"), on="asset_id", how="left"
    )
    with_assets = with_assets.withColumn(
        "asset_type",
        F.coalesce(
            F.col("asset_type"),
            F.when(F.col("asset_id").rlike("^wind_"), F.lit("wind_turbine"))
            .otherwise(F.lit("battery_bess")),
        ),
    )

    # Filter to key tags per asset type
    wind_tags = F.array([F.lit(t) for t in WIND_KEY_TAGS])
    battery_tags = F.array([F.lit(t) for t in BATTERY_KEY_TAGS])
    key_tags_col = F.when(
        F.col("asset_type") == "wind_turbine", wind_tags
    ).otherwise(battery_tags)

    key_tag_data = with_assets.filter(
        F.array_contains(key_tags_col, F.col("signal_name"))
    )

    # Z-scores per hour bucket
    zscore_data = key_tag_data.withColumn(
        "zscore",
        F.when(F.col("rolling_stddev") == 0, F.lit(0.0)).otherwise(
            (F.col("current_value") - F.col("rolling_mean"))
            / F.col("rolling_stddev")
        ),
    ).withColumn("is_anomalous", F.abs(F.col("zscore")) > 2.0)

    # Aggregate per hour + asset
    zscore_agg = zscore_data.groupBy("hour_bucket", "asset_id").agg(
        F.sum(F.when(F.col("is_anomalous"), 1).otherwise(0)).alias(
            "anomalous_count"
        ),
        F.count("*").alias("total_key_tags"),
        F.max_by("signal_name", F.abs(F.col("zscore"))).alias(
            "primary_risk_tag"
        ),
        F.max(F.abs(F.col("zscore"))).alias("max_zscore"),
    )

    scored = zscore_agg.withColumn(
        "health_score",
        F.when(F.col("total_key_tags") == 0, F.lit(1.0)).otherwise(
            1.0 - F.col("anomalous_count") / F.col("total_key_tags")
        ),
    )

    return scored.select(
        F.col("hour_bucket").alias("scored_at"),
        "asset_id",
        "health_score",
        "primary_risk_tag",
        F.round(F.col("max_zscore"), 1).alias("max_zscore"),
        F.round(F.lit(720.0) * F.pow(F.col("health_score"), 2), 1).alias(
            "estimated_hours_to_failure"
        ),
    )
