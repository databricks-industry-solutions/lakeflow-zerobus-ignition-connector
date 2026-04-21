"""Bronze to Silver transformations for the Zerobus connector pipeline.

Streams raw_tags (Zerobus landing table) and exposes:
- raw_throughput: bronze copy of raw_tags with lightweight added columns, deduped via AUTO CDC Type 1.
- aggregated_tags: 1-minute windowed aggregations for downstream analytics.
- parsed_tags: streaming table with pre-parsed asset_id and tag_name from tag_path.
- enriched_tags: streaming table with asset context via stream-static join.

raw_tags has CDF enabled (delta.enableChangeDataFeed). raw_throughput is built with AUTO CDC Type 1:
same key (event_time, tag_path, source_system) keeps latest by event_time; no history.

raw_tags schema (from Zerobus connector):
  event_time          BIGINT   - epoch microseconds
  ingestion_timestamp BIGINT   - epoch microseconds
  source_system       STRING
  tag_provider        STRING
  tag_path            STRING   - e.g. [agl_bess]AGL/.../SoC_pct
  numeric_value       DOUBLE
  string_value        STRING
  boolean_value       BOOLEAN
  quality             STRING
  quality_code        INT
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from agl_analytics.config import table

# CDF metadata columns are reserved by Delta and cannot exist in a table that has CDF enabled.
# DLT enables CDF on raw_throughput, so we must exclude all of them from the target and carry
# the commit timestamp under a non-reserved name for E2E latency.
_CDF_EXCEPT_COLUMNS = ["_change_type", "_commit_version", "_commit_timestamp"]


@dp.view(name="raw_tags_cdf")
def raw_tags_cdf():
    """Source view: raw_tags change data feed with lightweight added columns only (no groupBy, no drops).
    Copies _commit_timestamp to delta_commit_timestamp so the CDC target can keep it without
    using a reserved CDF column name.
    """
    return (
        spark.readStream.option("readChangeFeed", "true").table(table("raw_tags"))  # noqa: F821
        .withColumn(
            "event_timestamp",
            F.to_timestamp(F.col("event_time") / 1_000_000),
        )
        .withColumn("delta_commit_timestamp", F.col("_commit_timestamp"))
    )


dp.create_streaming_table(
    name="raw_throughput",
    comment="Deduplicated Bronze copy of raw_tags with added event_timestamp; AUTO CDC Type 1 dedup by (event_time, tag_path, source_system).",
    cluster_by=["event_time", "tag_path"],
)
dp.create_auto_cdc_flow(
    target="raw_throughput",
    source="raw_tags_cdf",
    keys=["event_time", "tag_path", "source_system"],
    sequence_by=F.col("event_time"),
    except_column_list=_CDF_EXCEPT_COLUMNS,
    stored_as_scd_type=1,
)


@dp.table(
    name="aggregated_tags",
    comment="1-minute aggregated tag values from raw_tags stream",
    cluster_by=["window_start", "tag_name"],
)
@dp.expect("valid_window", "window_start IS NOT NULL AND window_end IS NOT NULL")
@dp.expect("has_tag_name", "tag_name IS NOT NULL AND length(trim(tag_name)) > 0")
@dp.expect("valid_sample_count", "sample_count > 0")
def aggregated_tags():
    """Streaming table: 1-minute tumbling window aggregation of raw tags.

    Reads from bronze raw_throughput (same pipeline) and computes per tag_path:
    avg_value, min_value, max_value, stddev_value, sample_count.
    """
    return (
        spark.readStream.table("raw_throughput")  # noqa: F821
        .withColumn(
            "tag_value",
            F.coalesce(
                F.col("numeric_value"),
                F.when(F.col("boolean_value"), F.lit(1.0)).otherwise(F.lit(0.0)),
            ),
        )
        .withWatermark("event_timestamp", "1 minute")
        .groupBy(
            F.window("event_timestamp", "1 minute").alias("window"),
            "tag_path",
            "source_system",
            "tag_provider",
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
            F.col("tag_path").alias("tag_name"),
            "source_system",
            "tag_provider",
            "avg_value",
            "min_value",
            "max_value",
            "stddev_value",
            "sample_count",
        )
    )


@dp.table(
    name="parsed_tags",
    comment="Streaming table: pre-parsed raw tags with asset_id and tag_name extracted from tag_path",
    cluster_by=["event_timestamp", "asset_id"],
)
@dp.expect("valid_event_timestamp", "event_timestamp IS NOT NULL")
@dp.expect("has_asset_id", "asset_id IS NOT NULL AND length(trim(asset_id)) > 0")
@dp.expect("valid_quality_code", "quality IS NULL OR (quality >= 0 AND quality <= 255)")
@dp.expect_or_drop(
    "not_future_event",
    "event_timestamp <= current_timestamp() + INTERVAL 5 MINUTES",
)
def parsed_tags():
    """Streaming table: parses tag_path from raw_throughput into app-ready columns.

    Stays continuously fresh (unlike a MV which requires explicit refresh).
    Eliminates the need for the app to run a CTE on every query.
    Tag path: [provider]AGL/Australia/{State}/{Site}/Site01/{Asset}/{Subsystem}/{Signal}
    Extracts: asset_id = lower(site_asset), tag_name = lower(subsystem/signal).
    """
    strip_provider = r"^\[.*?\]"
    raw = spark.readStream.table("raw_throughput")  # noqa: F821

    parts = F.split(F.regexp_replace("tag_path", strip_provider, ""), "/")

    return (
        raw.withColumn("_p", parts)
        .filter(F.size("_p") >= 6)
        .select(
            F.to_timestamp(F.col("event_time") / 1000000).alias("event_timestamp"),
            F.to_timestamp(F.col("ingestion_timestamp") / 1000000).alias("ingest_timestamp"),
            F.col("delta_commit_timestamp"),
            F.lower(F.concat_ws("_", F.col("_p")[3], F.col("_p")[5])).alias("asset_id"),
            F.when(F.col("tag_provider") == "agl_bess", "battery_bess")
            .when(F.col("tag_provider") == "agl_grid", "grid_infrastructure")
            .when(F.col("tag_provider") == "agl_market", "market_data")
            .when(F.col("tag_provider") == "agl_cmms", "maintenance")
            .otherwise(F.col("tag_provider"))
            .alias("asset_type"),
            F.lower(
                F.array_join(F.slice("_p", 7, F.size("_p") - 6), "/")
            ).alias("tag_name"),
            F.coalesce(
                F.col("numeric_value"),
                F.when(F.col("boolean_value"), F.lit(1.0))
                .when(~F.col("boolean_value"), F.lit(0.0)),
            ).alias("tag_value"),
            F.col("string_value").alias("tag_value_str"),
            F.col("quality_code").alias("quality"),
            "source_system",
            F.coalesce(F.col("sdt_compressed"), F.lit(False)).alias("sdt_compressed"),
            F.coalesce(F.col("compression_ratio"), F.lit(0.0)).alias("compression_ratio"),
            F.coalesce(F.col("sdt_enabled"), F.lit(False)).alias("sdt_enabled"),
        )
    )


@dp.table(
    name="enriched_tags",
    comment="Streaming table: aggregated tags enriched with asset_id and signal_name via stream-static join",
    cluster_by=["window_start", "asset_id"],
)
@dp.expect("valid_window_start", "window_start IS NOT NULL")
@dp.expect("valid_sample_count", "sample_count >= 0")
def enriched_tags():
    """Streaming table: stream-static join of aggregated_tags with signal mapping.

    Streams from aggregated_tags and joins with static silver_signal_mapping.
    Resolves tag_path -> asset_id, signal_name, unit, source_domain.
    When silver_signal_mapping has no row, derives asset_id and signal_name from
    simulator-style tag_path [sim]asset_id/subsystem/signal (e.g. [sim]bess_site01_u01/battery/soc_pct).
    """
    # Stream-static join: stream from aggregated_tags, static read from signal_mapping
    agg = (
        spark.readStream.table(table("aggregated_tags"))  # noqa: F821
        .withWatermark("window_start", "30 seconds")
    )

    mappings = (
        spark.read.table(table("silver_signal_mapping"))  # noqa: F821
        .filter(F.col("active") == True)  # noqa: E712
        .select("tag_path", "asset_id", "signal_name", "unit", "source_domain")
    )

    joined = agg.join(mappings, agg.tag_name == mappings.tag_path, "left")

    # Derive asset_id and signal_name from tag paths when mapping is missing.
    # Supports two formats:
    # 1. [sim]asset_id/subsystem/signal (e.g., [sim]bess_site01_u01/battery/soc_pct)
    # 2. [agl_*]AGL/Australia/{State}/{Location}/Site01/{Asset}/{Subsystem}/{Signal}
    #    (e.g., [agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/SoC_pct)

    # Parse [sim] format
    sim_stripped = F.regexp_replace(F.col("tag_name"), r"^\[sim\]", "")
    sim_asset_id = F.when(
        F.col("tag_name").rlike(r"^\[sim\]"),
        F.element_at(F.split(sim_stripped, "/"), 1),
    )
    sim_signal_name = F.when(
        F.col("tag_name").rlike(r"^\[sim\]"),
        F.array_join(F.slice(F.split(sim_stripped, "/"), 2, 100), "/"),
    )

    # Parse [agl_*] format: strip provider, split by /
    # Parts (1-indexed): 1=AGL, 2=Australia, 3=State, 4=Location, 5=Site01, 6=Asset, 7=Subsystem, 8+=Signal
    strip_provider = r"^\[[^\]]+\]"
    agl_parts = F.split(F.regexp_replace(F.col("tag_name"), strip_provider, ""), "/")
    agl_asset_id = F.when(
        F.col("tag_name").rlike(r"^\[agl_"),
        F.lower(F.concat_ws("_", F.element_at(agl_parts, 4), F.element_at(agl_parts, 6))),
    )
    agl_signal_name = F.when(
        F.col("tag_name").rlike(r"^\[agl_"),
        F.lower(F.array_join(F.slice(agl_parts, 7, 100), "/")),
    )

    # Coalesce: agl first (more specific), then sim fallback
    derived_asset_id = F.coalesce(agl_asset_id, sim_asset_id)
    derived_signal_name = F.coalesce(agl_signal_name, sim_signal_name)

    return (
        joined.withColumn("_derived_asset_id", derived_asset_id)
        .withColumn("_derived_signal_name", derived_signal_name)
        .select(
            "window_start",
            "window_end",
            "tag_name",
            "source_system",
            "tag_provider",
            F.coalesce(
                mappings.asset_id, F.col("_derived_asset_id"), F.lit("unknown")
            ).alias("asset_id"),
            F.coalesce(
                mappings.signal_name,
                F.col("_derived_signal_name"),
                F.col("tag_name"),
            ).alias("signal_name"),
            "unit",
            "source_domain",
            "avg_value",
            "min_value",
            "max_value",
            "stddev_value",
            "sample_count",
        )
    )
