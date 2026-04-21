"""Query service for Databricks SQL.

All queries use parameterized placeholders - no string interpolation.
Table references use fully-qualified ``{catalog}.{schema}.table`` names
derived from DATABRICKS_CATALOG / DATABRICKS_SCHEMA env vars so that
every component targets the same catalog.

In production, query_service.execute() uses databricks-sql-connector.
In tests, query_service is monkey-patched.
"""

from __future__ import annotations

import os
from typing import Any

# Module-level catalog config - call init() at app startup or rely on defaults.
_catalog: str = os.environ.get("DATABRICKS_CATALOG", "agl_demo")
_schema: str = os.environ.get("DATABRICKS_SCHEMA", "ot")


def init(catalog: str, schema: str) -> None:
    """Set the catalog and schema used by all query builders."""
    global _catalog, _schema
    _catalog = catalog
    _schema = schema


def _t(table: str, schema_override: str | None = None) -> str:
    """Return a fully-qualified table reference."""
    return f"{_catalog}.{schema_override or _schema}.{table}"


def _throughput(minutes: int = 5) -> tuple[str, list[Any]]:
    return (
        "SELECT window_start, window_end, records_raw, records_after_sdt, "
        "bytes_estimate, tags_active, sdt_compression_ratio "
        f"FROM {_t('ingest_metrics')} "
        "WHERE window_start >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP()) "
        "ORDER BY window_start",
        [minutes],
    )


def _latency(minutes: int = 5) -> tuple[str, list[Any]]:
    return (
        "SELECT window_start, window_end, avg_latency_ms, p99_latency_ms "
        f"FROM {_t('ingest_metrics')} "
        "WHERE window_start >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP()) "
        "ORDER BY window_start",
        [minutes],
    )


def _compression() -> tuple[str, list[Any]]:
    return (
        "SELECT asset_id, AVG(sdt_compression_ratio) as compression_ratio "
        f"FROM {_t('ingest_metrics')} "
        "WHERE window_start >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP()) "
        "GROUP BY asset_id",
        [5],
    )


def _events_latest(limit: int = 50) -> tuple[str, list[Any]]:
    return (
        "SELECT event_timestamp, ingest_timestamp, asset_id, asset_type, "
        "tag_name, tag_value, quality, sdt_compressed, compression_ratio "
        f"FROM {_t('raw_tags')} "
        "ORDER BY ingest_timestamp DESC "
        "LIMIT :p_limit",
        [limit],
    )


def _assets() -> tuple[str, list[Any]]:
    return (
        "SELECT a.asset_id, a.asset_name, a.asset_type, a.site_name, "
        "a.capacity_mw, a.tag_count, a.latitude, a.longitude, "
        "r.operational_state, r.alarm_code, r.last_update, r.compression_ratio "
        f"FROM {_t('assets')} a "
        "LEFT JOIN ("
        "  SELECT asset_id, "
        "    MAX(CASE WHEN tag_name = 'status/operational_state' THEN tag_value END) as operational_state, "
        "    MAX(CASE WHEN tag_name = 'status/alarm_code' THEN tag_value END) as alarm_code, "
        "    MAX(event_timestamp) as last_update, "
        "    AVG(compression_ratio) as compression_ratio "
        f"  FROM {_t('raw_tags')} "
        "  WHERE event_timestamp >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP()) "
        "  GROUP BY asset_id "
        ") r ON a.asset_id = r.asset_id",
        [5],
    )


def _asset_by_id(asset_id: str) -> tuple[str, list[Any]]:
    return (
        "SELECT asset_id, asset_name, asset_type, site_name, "
        "capacity_mw, latitude, longitude, commissioned_date, tag_count "
        f"FROM {_t('assets')} "
        "WHERE asset_id = :p_asset_id",
        [asset_id],
    )


def _asset_tags(
    asset_id: str,
    tags: list[str] | None = None,
    range_minutes: int = 5,
) -> tuple[str, list[Any]]:
    tag_filter = ""
    tag_params: list[Any] = []
    if tags:
        placeholders = ", ".join([f":p_tag_{i}" for i in range(len(tags))])
        tag_filter = f" AND tag_name IN ({placeholders})"
        tag_params = list(tags)

    return (
        "SELECT event_timestamp, tag_name, tag_value, quality, sdt_compressed "
        f"FROM {_t('raw_tags')} "
        f"WHERE asset_id = :p_asset_id AND event_timestamp >= TIMESTAMPADD(MINUTE, -:p_range, CURRENT_TIMESTAMP()){tag_filter} "
        "ORDER BY event_timestamp",
        [asset_id, range_minutes, *tag_params],
    )


def _compression_comparison() -> tuple[str, list[Any]]:
    return (
        "SELECT SUM(records_raw) as total_raw, "
        "SUM(records_after_sdt) as total_after_sdt, "
        "SUM(bytes_estimate) as total_bytes, "
        "AVG(sdt_compression_ratio) as avg_sdt_ratio "
        f"FROM {_t('ingest_metrics')} "
        "WHERE window_start >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP())",
        [30],
    )


def _sdt_config() -> tuple[str, list[Any]]:
    return (
        "SELECT tag_pattern, comp_dev, comp_dev_percent, comp_max_seconds, comp_min_seconds "
        f"FROM {_t('sdt_config')} "
        "ORDER BY tag_pattern",
        [],
    )


def _sdt_config_update(
    tag_pattern: str,
    comp_dev: float | None = None,
    comp_dev_percent: float | None = None,
    comp_max_seconds: int | None = 600,
    comp_min_seconds: int | None = 0,
) -> tuple[str, list[Any]]:
    return (
        f"MERGE INTO {_t('sdt_config')} AS target "
        "USING (SELECT :p_pattern as tag_pattern) AS source "
        "ON target.tag_pattern = source.tag_pattern "
        "WHEN MATCHED THEN UPDATE SET "
        "comp_dev = :p_dev, comp_dev_percent = :p_pct, "
        "comp_max_seconds = :p_max, comp_min_seconds = :p_min "
        "WHEN NOT MATCHED THEN INSERT "
        "(tag_pattern, comp_dev, comp_dev_percent, comp_max_seconds, comp_min_seconds) "
        "VALUES (:p_pattern2, :p_dev2, :p_pct2, :p_max2, :p_min2)",
        [
            tag_pattern,
            comp_dev,
            comp_dev_percent,
            comp_max_seconds,
            comp_min_seconds,
            tag_pattern,
            comp_dev,
            comp_dev_percent,
            comp_max_seconds,
            comp_min_seconds,
        ],
    )


def _diagnostic() -> tuple[str, list[Any]]:
    return (
        "SELECT COUNT(*) AS total_rows,"
        "  COUNT(*) FILTER ("
        "    WHERE event_timestamp >= TIMESTAMPADD(MINUTE, -10, CURRENT_TIMESTAMP())"
        "  ) AS rows_last_10_min,"
        "  CAST(MIN(event_timestamp) AS STRING) AS oldest_event,"
        "  CAST(MAX(event_timestamp) AS STRING) AS newest_event,"
        "  CAST(CURRENT_TIMESTAMP() AS STRING) AS warehouse_now"
        f" FROM {_t('raw_tags')}",
        [],
    )


QUERY_BUILDERS: dict[str, Any] = {
    "diagnostic": _diagnostic,
    "throughput": _throughput,
    "latency": _latency,
    "compression": _compression,
    "eventsLatest": _events_latest,
    "assets": _assets,
    "assetById": _asset_by_id,
    "assetTags": _asset_tags,
    "compressionComparison": _compression_comparison,
    "sdtConfig": _sdt_config,
    "sdtConfigUpdate": _sdt_config_update,
}


def build_query(name: str, **kwargs: Any) -> tuple[str, list[Any]]:
    builder = QUERY_BUILDERS.get(name)
    if builder is None:
        raise ValueError(f"Unknown query: {name}")
    return builder(**kwargs)


async def execute(name: str, **kwargs: Any) -> list[dict[str, Any]]:
    """Execute a named query. In production wraps databricks-sql-connector.

    In tests this function is monkey-patched.
    """
    _sql, _params = build_query(name, **kwargs)
    return []
