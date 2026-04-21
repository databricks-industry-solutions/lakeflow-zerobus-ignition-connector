"""Query service for Databricks SQL (DBSQL warehouse).

All queries run via the Databricks Statement Execution API against the
app's SQL warehouse (DATABRICKS_WAREHOUSE_ID from the sql-warehouse
resource). Table references use fully-qualified {catalog}.{schema}.table
from APP_TARGET_CATALOG / APP_TARGET_SCHEMA (same as the SDP pipeline target).

The app reads from pipeline MVs where available:
- health_scores, revenue_risk, revenue_summary: MVs from SDP pipeline.
- parsed_tags: MV used for event/asset queries when USE_PARSED_TAGS=true (bundle default).
- raw_tags, asset_hierarchy, etc.: tables in the same catalog.schema.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem, StatementState


class QueryError(Exception):
    """Raised when a SQL query fails so callers can surface the message."""

    def __init__(self, query_name: str, message: str) -> None:
        self.query_name = query_name
        self.message = message
        super().__init__(f"Query {query_name} failed: {message}")


_catalog: str = os.environ.get(
    "APP_TARGET_CATALOG", os.environ.get("DATABRICKS_CATALOG", "ot_demo")
)
_schema: str = os.environ.get(
    "APP_TARGET_SCHEMA", os.environ.get("DATABRICKS_SCHEMA", "ot")
)

_client: WorkspaceClient | None = None
_warehouse_id: str = ""
_logger = logging.getLogger(__name__)

# Regex to strip Ignition tag provider prefix, e.g. [bess]
_STRIP_PROVIDER = r"^\[.*?\]"

# When True, queries read from the parsed_tags streaming table (continuously
# updated by SDP pipeline) instead of running the CTE inline. Set via
# USE_PARSED_TAGS=true env var.
_use_parsed_tags: bool = os.environ.get("USE_PARSED_TAGS", "").lower() in (
    "true",
    "1",
    "yes",
)


def init(catalog: str, schema: str) -> None:
    """Set the catalog and schema used by all query builders."""
    global _catalog, _schema
    _catalog = catalog
    _schema = schema
    _logger.warning(
        "Query service initialized: catalog=%s, schema=%s", _catalog, _schema
    )


def _t(table: str, schema_override: str | None = None) -> str:
    """Return a fully-qualified table reference."""
    return f"{_catalog}.{schema_override or _schema}.{table}"


# ---------------------------------------------------------------------------
# CTE helpers - transform connector raw_tags to app-expected columns
# ---------------------------------------------------------------------------

_parsed_tags_available: bool | None = None  # None = not yet checked
_parsed_tags_check_count: int = 0
_PARSED_TAGS_RECHECK_EVERY: int = 50  # re-probe after this many calls


def _check_parsed_tags() -> bool:
    """Check whether the parsed_tags table exists (cached after first success).

    Once confirmed, the result is cached permanently. If the table is not
    found, we re-check every N calls in case the pipeline has started since.
    """
    global _parsed_tags_available, _parsed_tags_check_count
    if _parsed_tags_available is True:
        return True
    # Throttle re-checks - only probe every N calls
    _parsed_tags_check_count += 1
    if (
        _parsed_tags_available is False
        and _parsed_tags_check_count % _PARSED_TAGS_RECHECK_EVERY != 0
    ):
        return False
    try:
        client = _get_client()
        client.statement_execution.execute_statement(
            warehouse_id=_warehouse_id,
            catalog=_catalog,
            schema=_schema,
            statement=f"SELECT 1 FROM {_t('parsed_tags')} LIMIT 0",
            wait_timeout="10s",
        )
        _parsed_tags_available = True
        _logger.info("parsed_tags table confirmed available")
        return True
    except Exception:
        _parsed_tags_available = False
        _logger.info(
            "parsed_tags not available yet, falling back to inline CTE on raw_tags"
        )
        return False


def _event_cte() -> str:
    """CTE: connector raw_tags -> app event columns.

    When USE_PARSED_TAGS=true AND the parsed_tags streaming table exists,
    reads directly from it (continuously updated by SDP pipeline - much
    faster for the app).

    Otherwise falls back to inline CTE parsing against raw_tags.
    Tag path structure:
      [provider]Demo/Region/{Site}/Site01/{Asset}/{Subsystem}/{Signal}
    Extracts asset_id as lower(site_asset), tag_name as lower(subsystem/signal).
    """
    if _use_parsed_tags and _check_parsed_tags():
        return f"WITH events AS (SELECT * FROM {_t('parsed_tags')})"

    pat = _STRIP_PROVIDER
    return (
        "WITH _paths AS ("
        f"  SELECT *, SPLIT(REGEXP_REPLACE(tag_path, '{pat}', ''), '/') AS _p"
        f"  FROM {_t('raw_tags')}"
        "), events AS ("
        "  SELECT"
        "    TIMESTAMP_MICROS(event_time) AS event_timestamp,"
        "    TIMESTAMP_MICROS(ingestion_timestamp) AS ingest_timestamp,"
        "    CASE WHEN SIZE(_p) >= 6 THEN LOWER(CONCAT(_p[3], '_', _p[5]))"
        "         ELSE COALESCE(LOWER(tag_provider), 'unknown') END AS asset_id,"
        "    CASE"
        "      WHEN tag_provider RLIKE '(?i)(^|_)bess$' THEN 'battery_bess'"
        "      WHEN tag_provider RLIKE '(?i)(^|_)grid$' THEN 'grid_infrastructure'"
        "      WHEN tag_provider RLIKE '(?i)(^|_)market$' THEN 'market_data'"
        "      WHEN tag_provider RLIKE '(?i)(^|_)cmms$' THEN 'maintenance'"
        "      ELSE COALESCE(tag_provider, 'unknown')"
        "    END AS asset_type,"
        "    CASE WHEN SIZE(_p) >= 7 THEN LOWER(ARRAY_JOIN(SLICE(_p, 7, SIZE(_p) - 6), '/'))"
        "         WHEN SIZE(_p) >= 1 THEN LOWER(_p[SIZE(_p) - 1])"
        "         ELSE LOWER(REGEXP_REPLACE(tag_path, '" + pat + "', ''))"
        "    END AS tag_name,"
        "    COALESCE(numeric_value,"
        "      CASE WHEN boolean_value THEN 1.0"
        "           WHEN boolean_value = false THEN 0.0 END"
        "    ) AS tag_value,"
        "    string_value AS tag_value_str,"
        "    quality_code AS quality,"
        "    source_system,"
        "    COALESCE(sdt_compressed, false) AS sdt_compressed,"
        "    COALESCE(compression_ratio, 0.0) AS compression_ratio"
        "  FROM _paths"
        ")"
    )


# Metric windows are 5 seconds. records_raw / records_after_sdt are counts per window;
# divide by this to get events/sec for throughput.
METRIC_WINDOW_SECONDS = 5


def _metrics_cte(lookback_minutes: int = 60, source: str = "raw_tags") -> str:
    """CTE: aggregate into 5-second metric windows from raw_tags or raw_throughput.

    source: 'raw_tags' (Zerobus landing table) or 'raw_throughput' (deduped CDF stream).
    Same schema for both; raw_throughput is deduped so counts may be lower.

    Latency (avg_latency_ms, p99_latency_ms) = (ingestion_timestamp - event_time) in ms.
    That is in-process only (tag → connector in the Ignition JVM). It does NOT include
    network (e.g. Australia → US), Zerobus, or Delta commit. Use E2E latency for that.
    """
    table = source if source in ("raw_tags", "raw_throughput") else "raw_tags"
    # Guardrails:
    # - Ignore negative latency rows (ingestion before event_time), usually from source clock skew.
    # - Ignore extreme outliers (>1h) so a few bad rows do not distort dashboard KPIs.
    # - Ignore future event timestamps beyond a small tolerance window.
    return (
        "WITH metrics AS ("
        "  SELECT"
        "    TIMESTAMP_MICROS(CAST(FLOOR(event_time / 5000000) * 5000000 AS BIGINT)) AS window_start,"
        "    TIMESTAMP_MICROS(CAST(FLOOR(event_time / 5000000) * 5000000 + 5000000 AS BIGINT)) AS window_end,"
        "    CAST(ROUND(COUNT(*) / GREATEST(0.01, 1.0 - COALESCE(AVG(compression_ratio), 0) / 100.0)) AS BIGINT) AS records_raw,"
        "    COUNT(*) AS records_after_sdt,"
        "    COUNT(*) * 100 AS bytes_estimate,"
        "    AVG(CAST(ingestion_timestamp - event_time AS DOUBLE) / 1000.0) AS avg_latency_ms,"
        "    PERCENTILE_APPROX(CAST(ingestion_timestamp - event_time AS DOUBLE) / 1000.0, 0.99) AS p99_latency_ms,"
        "    COUNT(DISTINCT tag_path) AS tags_active,"
        "    COALESCE(AVG(NULLIF(compression_ratio, 0)), 0) AS sdt_compression_ratio,"
        "    BOOL_OR(COALESCE(sdt_enabled, sdt_compressed, false)) AS sdt_enabled"
        f"  FROM {_t(table)}"
        f"  WHERE TIMESTAMP_MICROS(event_time) >= TIMESTAMPADD(MINUTE, -{lookback_minutes}, CURRENT_TIMESTAMP())"
        "    AND event_time IS NOT NULL"
        "    AND ingestion_timestamp IS NOT NULL"
        "    AND event_time <= UNIX_MICROS(TIMESTAMPADD(MINUTE, 5, CURRENT_TIMESTAMP()))"
        "    AND (CAST(ingestion_timestamp - event_time AS DOUBLE) BETWEEN 0 AND 3600000000)"
        "  GROUP BY 1, 2"
        ")"
    )


# ---------------------------------------------------------------------------
# Metric queries (derived from raw_tags inline)
# ---------------------------------------------------------------------------


def _throughput(minutes: int = 5, source: str = "raw_tags") -> tuple[str, list[Any]]:
    return (
        f"{_metrics_cte(minutes * 2, source)} "
        "SELECT window_start, window_end, records_raw, records_after_sdt, "
        "bytes_estimate, tags_active, sdt_compression_ratio, sdt_enabled "
        "FROM metrics "
        "WHERE window_start >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP()) "
        "ORDER BY window_start",
        [minutes],
    )


def _latency(minutes: int = 5, source: str = "raw_tags") -> tuple[str, list[Any]]:
    return (
        f"{_metrics_cte(minutes * 2, source)} "
        "SELECT window_start, window_end, avg_latency_ms, p99_latency_ms "
        "FROM metrics "
        "WHERE window_start >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP()) "
        "ORDER BY window_start",
        [minutes],
    )


def _latency_e2e(minutes: int = 5) -> tuple[str, list[Any]]:
    """E2E latency from raw_throughput.

    Prefers CDF _commit_timestamp (tag time → Delta commit) when present; otherwise
    uses ingestion_timestamp so the query runs in environments where CDF columns
    are not exposed on the AUTO CDC target.
    """
    table_name = _t("raw_throughput")
    return (
        "WITH cdf AS ("
        "  SELECT event_time, _commit_timestamp"
        f"  FROM table_changes('{table_name}', TIMESTAMPADD(MINUTE, -:p_lookback, CURRENT_TIMESTAMP()))"
        "  WHERE _change_type != 'update_preimage'"
        "    AND event_time IS NOT NULL"
        "    AND _commit_timestamp IS NOT NULL"
        "), e2e_metrics AS ("
        "  SELECT"
        "    TIMESTAMP_MICROS(CAST(FLOOR(event_time / 5000000) * 5000000 AS BIGINT)) AS window_start,"
        "    TIMESTAMP_MICROS(CAST(FLOOR(event_time / 5000000) * 5000000 + 5000000 AS BIGINT)) AS window_end,"
        "    AVG(CAST(UNIX_MICROS(_commit_timestamp) - event_time AS DOUBLE) / 1000.0) AS avg_e2e_latency_ms,"
        "    PERCENTILE_APPROX(CAST(UNIX_MICROS(_commit_timestamp) - event_time AS DOUBLE) / 1000.0, 0.99) AS p99_e2e_latency_ms,"
        "    AVG(CAST(UNIX_MICROS(CURRENT_TIMESTAMP()) - UNIX_MICROS(_commit_timestamp) AS DOUBLE) / 1000.0) AS avg_delta_to_app_ms,"
        "    PERCENTILE_APPROX(CAST(UNIX_MICROS(CURRENT_TIMESTAMP()) - UNIX_MICROS(_commit_timestamp) AS DOUBLE) / 1000.0, 0.99) AS p99_delta_to_app_ms"
        "  FROM cdf"
        "  WHERE event_time <= UNIX_MICROS(TIMESTAMPADD(MINUTE, 5, CURRENT_TIMESTAMP()))"
        "    AND (CAST(UNIX_MICROS(_commit_timestamp) - event_time AS DOUBLE) BETWEEN 0 AND 3600000000)"
        "    AND (CAST(UNIX_MICROS(CURRENT_TIMESTAMP()) - UNIX_MICROS(_commit_timestamp) AS DOUBLE) BETWEEN 0 AND 3600000000)"
        "  GROUP BY 1, 2"
        ") "
        "SELECT window_start, window_end, avg_e2e_latency_ms, p99_e2e_latency_ms, avg_delta_to_app_ms, p99_delta_to_app_ms "
        "FROM e2e_metrics "
        "WHERE window_start >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP()) "
        "ORDER BY window_start",
        [minutes * 2, minutes],
    )


def _compression() -> tuple[str, list[Any]]:
    pat = _STRIP_PROVIDER
    return (
        "WITH _paths AS ("
        f"  SELECT *, SPLIT(REGEXP_REPLACE(tag_path, '{pat}', ''), '/') AS _p"
        f"  FROM {_t('raw_tags')}"
        "  WHERE TIMESTAMP_MICROS(event_time) >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP())"
        ") "
        "SELECT LOWER(CONCAT(_p[3], '_', _p[5])) AS asset_id,"
        "  AVG(COALESCE(compression_ratio, 0)) AS compression_ratio "
        "FROM _paths "
        "WHERE SIZE(_p) >= 6 "
        "GROUP BY 1",
        [5],
    )


# ---------------------------------------------------------------------------
# Event queries (from raw_tags via CTE)
# ---------------------------------------------------------------------------


def _events_latest(limit: int = 50) -> tuple[str, list[Any]]:
    return (
        f"{_event_cte()} "
        "SELECT event_timestamp, ingest_timestamp, asset_id, asset_type, "
        "tag_name, tag_value, quality, sdt_compressed, compression_ratio "
        "FROM events "
        "ORDER BY ingest_timestamp DESC "
        "LIMIT :p_limit",
        [limit],
    )


# ---------------------------------------------------------------------------
# Asset queries
# ---------------------------------------------------------------------------


def _assets() -> tuple[str, list[Any]]:
    return (
        f"{_event_cte()}, "
        "latest AS ("
        "  SELECT asset_id,"
        "    MAX(CASE WHEN tag_name = 'mode' THEN tag_value_str END) AS operational_state,"
        "    MAX(CASE WHEN tag_name = 'criticalalarmactive'"
        "         THEN CASE WHEN tag_value = 1.0 THEN 'CRITICAL' ELSE 'OK' END END) AS alarm_code,"
        "    MAX(event_timestamp) AS last_update,"
        "    AVG(compression_ratio) AS compression_ratio"
        "  FROM events"
        "  WHERE event_timestamp >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP())"
        "  GROUP BY asset_id"
        ") "
        "SELECT a.asset_id, a.asset_name, a.asset_type, a.site_name, "
        "a.capacity_mw, a.tag_count, a.latitude, a.longitude, "
        "r.operational_state, r.alarm_code, r.last_update, r.compression_ratio "
        f"FROM {_t('asset_hierarchy')} a "
        "LEFT JOIN latest r ON a.asset_id = r.asset_id "
        "WHERE a.active = true AND a.asset_type NOT IN ('enterprise', 'site')",
        [5],
    )


def _asset_by_id(asset_id: str) -> tuple[str, list[Any]]:
    return (
        "SELECT asset_id, asset_name, asset_type, site_name, "
        "capacity_mw, latitude, longitude, tag_count "
        f"FROM {_t('asset_hierarchy')} "
        "WHERE asset_id = :p_asset_id AND active = true",
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
        f"{_event_cte()} "
        "SELECT event_timestamp, tag_name, tag_value, quality, sdt_compressed "
        "FROM events "
        f"WHERE asset_id = :p_asset_id AND event_timestamp >= TIMESTAMPADD(MINUTE, -:p_range, CURRENT_TIMESTAMP()){tag_filter} "
        "ORDER BY event_timestamp",
        [asset_id, range_minutes, *tag_params],
    )


# ---------------------------------------------------------------------------
# Compression / SDT config
# ---------------------------------------------------------------------------


def _compression_comparison() -> tuple[str, list[Any]]:
    return (
        f"{_metrics_cte(60)} "
        "SELECT SUM(records_raw) as total_raw, "
        "SUM(records_after_sdt) as total_after_sdt, "
        "SUM(bytes_estimate) as total_bytes, "
        "AVG(sdt_compression_ratio) as avg_sdt_ratio "
        "FROM metrics "
        "WHERE window_start >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP())",
        [30],
    )


def _raw_tags_storage_metrics() -> tuple[str, list[Any]]:
    """Run DESCRIBE DETAIL on raw_tags to get Delta storage metrics.
    Returns a single row with sizeInBytes, numFiles, etc.
    """
    table = f"{_catalog}.{_schema}.raw_tags"
    return (f"DESCRIBE DETAIL {table}", [])


def _raw_tags_total_count() -> tuple[str, list[Any]]:
    """Total row count in raw_tags (used to scale Delta size to a time window)."""
    return (f"SELECT COUNT(*) AS total_rows FROM {_t('raw_tags')}", [])


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


# === Analytics queries (APP-PRD) ===


def _health_scores() -> tuple[str, list[Any]]:
    """Get latest health scores per asset."""
    return (
        "SELECT scored_at, asset_id, health_score, primary_risk_tag, "
        "risk_description, anomaly_tags, estimated_hours_to_failure "
        f"FROM {_t('health_scores')} "
        "ORDER BY health_score ASC",
        [],
    )


def _revenue_risk() -> tuple[str, list[Any]]:
    """Get revenue at risk per asset for high-price windows."""
    return (
        "SELECT computed_at, asset_id, risk_window_start, risk_window_end, "
        "forecast_price_aud_mwh, capacity_mw AS asset_capacity_mw, health_score, "
        "trip_probability, revenue_at_risk_aud, recommended_action "
        f"FROM {_t('revenue_risk')} "
        "ORDER BY revenue_at_risk_aud DESC",
        [],
    )


def _nem_prices(hours: int = 24) -> tuple[str, list[Any]]:
    """Get recent NEM dispatch prices."""
    return (
        "SELECT interval_start, interval_end, region, price_aud_mwh, demand_mw "
        f"FROM {_t('nem_prices')} "
        "WHERE interval_start >= TIMESTAMPADD(HOUR, -:p_hours, CURRENT_TIMESTAMP()) "
        "ORDER BY interval_start DESC",
        [hours],
    )


def _price_forecast() -> tuple[str, list[Any]]:
    """Get 48-hour price forecast."""
    return (
        "SELECT forecast_timestamp, target_interval, region, "
        "forecast_price_aud_mwh, confidence "
        f"FROM {_t('price_forecast')} "
        "ORDER BY target_interval",
        [],
    )


def _revenue_summary() -> tuple[str, list[Any]]:
    """Get total revenue at risk summary."""
    return (
        "SELECT COUNT(DISTINCT asset_id) as assets_at_risk, "
        "SUM(revenue_at_risk_aud) as total_revenue_at_risk_aud, "
        "AVG(health_score) as avg_health_score, "
        "MIN(risk_window_start) as next_risk_window "
        f"FROM {_t('revenue_risk')} "
        "WHERE revenue_at_risk_aud > 0",
        [],
    )


# ---------------------------------------------------------------------------
# Asset Framework queries
# ---------------------------------------------------------------------------


def _hierarchy() -> tuple[str, list[Any]]:
    """Recursive CTE to get full asset tree with depth and child count."""
    return (
        "WITH RECURSIVE tree AS ("
        f"  SELECT asset_id, parent_asset_id, asset_name, asset_type, template_id, "
        "    site_name, description, capacity_mw, latitude, longitude, tag_count, active, 0 AS depth "
        f"  FROM {_t('asset_hierarchy')} "
        "  WHERE parent_asset_id IS NULL AND active = true "
        "  UNION ALL "
        "  SELECT h.asset_id, h.parent_asset_id, h.asset_name, h.asset_type, h.template_id, "
        "    h.site_name, h.description, h.capacity_mw, h.latitude, h.longitude, h.tag_count, h.active, t.depth + 1 "
        f"  FROM {_t('asset_hierarchy')} h "
        "  JOIN tree t ON h.parent_asset_id = t.asset_id "
        "  WHERE h.active = true"
        "), child_counts AS ("
        f"  SELECT parent_asset_id, COUNT(*) AS child_count "
        f"  FROM {_t('asset_hierarchy')} WHERE active = true "
        "  GROUP BY parent_asset_id"
        ") "
        "SELECT tree.asset_id, tree.parent_asset_id, tree.asset_name, tree.asset_type, "
        "tree.template_id, tree.site_name, tree.description, "
        "tree.capacity_mw, tree.latitude, tree.longitude, tree.tag_count, tree.depth, "
        "COALESCE(cc.child_count, 0) AS child_count "
        "FROM tree "
        "LEFT JOIN child_counts cc ON tree.asset_id = cc.parent_asset_id "
        "ORDER BY tree.depth, tree.asset_name",
        [],
    )


def _hierarchy_asset(asset_id: str) -> tuple[str, list[Any]]:
    """Single asset with template info."""
    return (
        "SELECT h.asset_id, h.parent_asset_id, h.asset_name, h.asset_type, "
        "h.template_id, h.site_name, h.description, "
        "h.capacity_mw, h.latitude, h.longitude, h.tag_count, h.active, "
        "t.template_name, t.base_asset_type AS template_base_type "
        f"FROM {_t('asset_hierarchy')} h "
        f"LEFT JOIN {_t('asset_templates')} t ON h.template_id = t.template_id "
        "WHERE h.asset_id = :p_asset_id",
        [asset_id],
    )


def _hierarchy_create(
    asset_id: str,
    asset_name: str,
    asset_type: str,
    parent_asset_id: str | None = None,
    template_id: str | None = None,
    site_name: str | None = None,
    description: str | None = None,
    capacity_mw: float | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    tag_count: int | None = None,
) -> tuple[str, list[Any]]:
    return (
        f"INSERT INTO {_t('asset_hierarchy')} "
        "(asset_id, parent_asset_id, asset_name, asset_type, template_id, site_name, description, "
        "capacity_mw, latitude, longitude, tag_count) "
        "VALUES (:p_id, :p_parent, :p_name, :p_type, :p_template, :p_site, :p_desc, "
        ":p_capacity, :p_lat, :p_lon, :p_tags)",
        [
            asset_id,
            parent_asset_id,
            asset_name,
            asset_type,
            template_id,
            site_name,
            description,
            capacity_mw,
            latitude,
            longitude,
            tag_count,
        ],
    )


def _hierarchy_update(
    asset_id: str,
    asset_name: str | None = None,
    asset_type: str | None = None,
    template_id: str | None = None,
    site_name: str | None = None,
    description: str | None = None,
    capacity_mw: float | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    tag_count: int | None = None,
) -> tuple[str, list[Any]]:
    return (
        f"MERGE INTO {_t('asset_hierarchy')} AS target "
        "USING (SELECT :p_id AS asset_id) AS source "
        "ON target.asset_id = source.asset_id "
        "WHEN MATCHED THEN UPDATE SET "
        "asset_name = COALESCE(:p_name, target.asset_name), "
        "asset_type = COALESCE(:p_type, target.asset_type), "
        "template_id = COALESCE(:p_template, target.template_id), "
        "site_name = COALESCE(:p_site, target.site_name), "
        "description = COALESCE(:p_desc, target.description), "
        "capacity_mw = COALESCE(:p_capacity, target.capacity_mw), "
        "latitude = COALESCE(:p_lat, target.latitude), "
        "longitude = COALESCE(:p_lon, target.longitude), "
        "tag_count = COALESCE(:p_tags, target.tag_count), "
        "updated_at = CURRENT_TIMESTAMP()",
        [
            asset_id,
            asset_name,
            asset_type,
            template_id,
            site_name,
            description,
            capacity_mw,
            latitude,
            longitude,
            tag_count,
        ],
    )


def _hierarchy_delete(asset_id: str) -> tuple[str, list[Any]]:
    """Soft delete: set active=false for this asset and all descendants."""
    return (
        "WITH RECURSIVE descendants AS ("
        f"  SELECT asset_id FROM {_t('asset_hierarchy')} WHERE asset_id = :p_id "
        "  UNION ALL "
        f"  SELECT h.asset_id FROM {_t('asset_hierarchy')} h "
        "  JOIN descendants d ON h.parent_asset_id = d.asset_id"
        ") "
        f"MERGE INTO {_t('asset_hierarchy')} AS target "
        "USING descendants AS source "
        "ON target.asset_id = source.asset_id "
        "WHEN MATCHED THEN UPDATE SET active = false, updated_at = CURRENT_TIMESTAMP()",
        [asset_id],
    )


def _hierarchy_move(
    asset_id: str, new_parent_id: str | None = None
) -> tuple[str, list[Any]]:
    return (
        f"UPDATE {_t('asset_hierarchy')} "
        "SET parent_asset_id = :p_parent, updated_at = CURRENT_TIMESTAMP() "
        "WHERE asset_id = :p_id",
        [new_parent_id, asset_id],
    )


def _templates_list() -> tuple[str, list[Any]]:
    """All templates with attribute count and asset usage count."""
    return (
        "SELECT t.template_id, t.template_name, t.description, t.base_asset_type, "
        "COUNT(DISTINCT ta.attribute_id) AS attribute_count, "
        "COUNT(DISTINCT h.asset_id) AS asset_count "
        f"FROM {_t('asset_templates')} t "
        f"LEFT JOIN {_t('template_attributes')} ta ON t.template_id = ta.template_id "
        f"LEFT JOIN {_t('asset_hierarchy')} h ON t.template_id = h.template_id AND h.active = true "
        "GROUP BY t.template_id, t.template_name, t.description, t.base_asset_type "
        "ORDER BY t.template_name",
        [],
    )


def _template_by_id(template_id: str) -> tuple[str, list[Any]]:
    """Template detail with attributes and assets using it."""
    return (
        "SELECT t.template_id, t.template_name, t.description, t.base_asset_type, "
        "ta.attribute_id, ta.attribute_name, ta.data_type, ta.unit, "
        "ta.default_value, ta.is_required, ta.sort_order, ta.tag_pattern "
        f"FROM {_t('asset_templates')} t "
        f"LEFT JOIN {_t('template_attributes')} ta ON t.template_id = ta.template_id "
        "WHERE t.template_id = :p_id "
        "ORDER BY ta.sort_order",
        [template_id],
    )


def _template_assets(template_id: str) -> tuple[str, list[Any]]:
    """Assets using a given template."""
    return (
        "SELECT asset_id, asset_name, asset_type, site_name "
        f"FROM {_t('asset_hierarchy')} "
        "WHERE template_id = :p_id AND active = true "
        "ORDER BY asset_name",
        [template_id],
    )


def _template_create(
    template_id: str,
    template_name: str,
    base_asset_type: str,
    description: str | None = None,
) -> tuple[str, list[Any]]:
    return (
        f"INSERT INTO {_t('asset_templates')} "
        "(template_id, template_name, description, base_asset_type) "
        "VALUES (:p_id, :p_name, :p_desc, :p_type)",
        [template_id, template_name, description, base_asset_type],
    )


def _template_update(
    template_id: str,
    template_name: str | None = None,
    description: str | None = None,
    base_asset_type: str | None = None,
) -> tuple[str, list[Any]]:
    return (
        f"MERGE INTO {_t('asset_templates')} AS target "
        "USING (SELECT :p_id AS template_id) AS source "
        "ON target.template_id = source.template_id "
        "WHEN MATCHED THEN UPDATE SET "
        "template_name = COALESCE(:p_name, target.template_name), "
        "description = COALESCE(:p_desc, target.description), "
        "base_asset_type = COALESCE(:p_type, target.base_asset_type), "
        "updated_at = CURRENT_TIMESTAMP()",
        [template_id, template_name, description, base_asset_type],
    )


def _template_delete(template_id: str) -> tuple[str, list[Any]]:
    """Delete template only if no assets reference it."""
    return (
        f"DELETE FROM {_t('asset_templates')} "
        "WHERE template_id = :p_id "
        f"AND NOT EXISTS (SELECT 1 FROM {_t('asset_hierarchy')} WHERE template_id = :p_id2 AND active = true)",
        [template_id, template_id],
    )


def _template_attr_create(
    attribute_id: str,
    template_id: str,
    attribute_name: str,
    data_type: str,
    unit: str | None = None,
    default_value: str | None = None,
    is_required: bool = False,
    sort_order: int = 0,
    tag_pattern: str | None = None,
) -> tuple[str, list[Any]]:
    return (
        f"INSERT INTO {_t('template_attributes')} "
        "(attribute_id, template_id, attribute_name, data_type, unit, default_value, is_required, sort_order, tag_pattern) "
        "VALUES (:p_id, :p_tpl, :p_name, :p_dtype, :p_unit, :p_default, :p_required, :p_sort, :p_tag_pattern)",
        [
            attribute_id,
            template_id,
            attribute_name,
            data_type,
            unit,
            default_value,
            is_required,
            sort_order,
            tag_pattern,
        ],
    )


def _template_attr_update(
    attribute_id: str,
    attribute_name: str | None = None,
    data_type: str | None = None,
    unit: str | None = None,
    default_value: str | None = None,
    is_required: bool | None = None,
    sort_order: int | None = None,
    tag_pattern: str | None = None,
) -> tuple[str, list[Any]]:
    return (
        f"MERGE INTO {_t('template_attributes')} AS target "
        "USING (SELECT :p_id AS attribute_id) AS source "
        "ON target.attribute_id = source.attribute_id "
        "WHEN MATCHED THEN UPDATE SET "
        "attribute_name = COALESCE(:p_name, target.attribute_name), "
        "data_type = COALESCE(:p_dtype, target.data_type), "
        "unit = COALESCE(:p_unit, target.unit), "
        "default_value = COALESCE(:p_default, target.default_value), "
        "is_required = COALESCE(:p_required, target.is_required), "
        "sort_order = COALESCE(:p_sort, target.sort_order), "
        "tag_pattern = COALESCE(:p_tag_pattern, target.tag_pattern)",
        [
            attribute_id,
            attribute_name,
            data_type,
            unit,
            default_value,
            is_required,
            sort_order,
            tag_pattern,
        ],
    )


def _template_attr_delete(attribute_id: str) -> tuple[str, list[Any]]:
    return (
        f"DELETE FROM {_t('template_attributes')} WHERE attribute_id = :p_id",
        [attribute_id],
    )


def _apply_template(asset_id: str, template_id: str) -> tuple[str, list[Any]]:
    """Insert default attribute values from template for an asset."""
    return (
        f"MERGE INTO {_t('asset_attribute_values')} AS target "
        "USING ("
        f"  SELECT :p_asset AS asset_id, attribute_id, default_value AS value "
        f"  FROM {_t('template_attributes')} WHERE template_id = :p_tpl"
        ") AS source "
        "ON target.asset_id = source.asset_id AND target.attribute_id = source.attribute_id "
        "WHEN NOT MATCHED THEN INSERT (asset_id, attribute_id, value) "
        "VALUES (source.asset_id, source.attribute_id, source.value)",
        [asset_id, template_id],
    )


def _asset_attr_values(asset_id: str) -> tuple[str, list[Any]]:
    """Get attribute values for an asset, joined with attribute metadata."""
    return (
        "SELECT av.attribute_id, ta.attribute_name, ta.data_type, ta.unit, "
        "ta.is_required, av.value, av.updated_at, ta.tag_pattern "
        f"FROM {_t('asset_attribute_values')} av "
        f"JOIN {_t('template_attributes')} ta ON av.attribute_id = ta.attribute_id "
        "WHERE av.asset_id = :p_id "
        "ORDER BY ta.sort_order",
        [asset_id],
    )


def _asset_attr_values_update(
    asset_id: str,
    attribute_id: str,
    value: str | None = None,
) -> tuple[str, list[Any]]:
    return (
        f"MERGE INTO {_t('asset_attribute_values')} AS target "
        "USING (SELECT :p_asset AS asset_id, :p_attr AS attribute_id) AS source "
        "ON target.asset_id = source.asset_id AND target.attribute_id = source.attribute_id "
        "WHEN MATCHED THEN UPDATE SET value = :p_value, updated_at = CURRENT_TIMESTAMP() "
        "WHEN NOT MATCHED THEN INSERT (asset_id, attribute_id, value) "
        "VALUES (:p_asset2, :p_attr2, :p_value2)",
        [asset_id, attribute_id, value, asset_id, attribute_id, value],
    )


def _asset_live_attr_values(asset_id: str) -> tuple[str, list[Any]]:
    """Resolve live tag values for an asset's bound template attributes."""
    return (
        f"{_event_cte()}, "
        "latest AS ( "
        "  SELECT asset_id, tag_name, tag_value, event_timestamp, "
        "    ROW_NUMBER() OVER (PARTITION BY asset_id, tag_name ORDER BY event_timestamp DESC) AS rn "
        "  FROM events "
        "  WHERE asset_id = :p_id "
        "    AND event_timestamp >= current_timestamp() - INTERVAL 10 MINUTES "
        ") "
        "SELECT ta.attribute_id, ta.attribute_name, ta.tag_pattern, "
        "  l.tag_value AS live_value, l.event_timestamp AS live_at "
        f"FROM {_t('asset_attribute_values')} av "
        f"JOIN {_t('template_attributes')} ta ON av.attribute_id = ta.attribute_id "
        "LEFT JOIN latest l ON l.asset_id = :p_id2 AND l.tag_name = ta.tag_pattern AND l.rn = 1 "
        "WHERE av.asset_id = :p_id3 AND ta.tag_pattern IS NOT NULL "
        "ORDER BY ta.sort_order",
        [asset_id, asset_id, asset_id],
    )


def _hierarchy_asset_tags(
    asset_id: str,
    minutes: int = 60,
    include_unmapped: bool = True,
) -> tuple[str, list[Any]]:
    """Catalog tags for one hierarchy asset with latest live values."""
    return (
        f"{_event_cte()}, "
        "latest_events AS ( "
        "  SELECT asset_id, tag_name, tag_value, tag_value_str, quality, event_timestamp, "
        "    sdt_compressed, compression_ratio, "
        "    ROW_NUMBER() OVER (PARTITION BY asset_id, tag_name ORDER BY event_timestamp DESC) AS rn "
        "  FROM events "
        "  WHERE asset_id = :p_asset_id "
        "    AND event_timestamp >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP()) "
        "), mapped_tags AS ( "
        "  SELECT hierarchy_asset_id AS asset_id, normalized_tag_name AS tag_name, "
        "    MIN(tag_path) AS tag_path, MAX(unit) AS unit, MAX(source_domain) AS source_domain "
        f"  FROM {_t('silver_signal_mapping_normalized')} "
        "  WHERE COALESCE(active, true) = true AND hierarchy_asset_id = :p_asset_id2 "
        "  GROUP BY hierarchy_asset_id, normalized_tag_name "
        "), mapped_rows AS ( "
        "  SELECT m.asset_id, m.tag_name, m.tag_path, m.unit, m.source_domain, "
        "    true AS is_mapped, "
        "    l.tag_value AS live_value, l.tag_value_str AS live_value_str, "
        "    l.quality, l.event_timestamp AS live_at, "
        "    l.sdt_compressed, l.compression_ratio "
        "  FROM mapped_tags m "
        "  LEFT JOIN latest_events l "
        "    ON l.asset_id = m.asset_id AND l.tag_name = m.tag_name AND l.rn = 1 "
        "), unmapped_rows AS ( "
        "  SELECT l.asset_id, l.tag_name, CAST(NULL AS STRING) AS tag_path, "
        "    CAST(NULL AS STRING) AS unit, CAST(NULL AS STRING) AS source_domain, "
        "    false AS is_mapped, "
        "    l.tag_value AS live_value, l.tag_value_str AS live_value_str, "
        "    l.quality, l.event_timestamp AS live_at, "
        "    l.sdt_compressed, l.compression_ratio "
        "  FROM latest_events l "
        "  WHERE l.rn = 1 "
        "    AND NOT EXISTS ("
        "      SELECT 1 FROM mapped_tags m "
        "      WHERE m.asset_id = l.asset_id AND m.tag_name = l.tag_name"
        "    ) "
        ") "
        "SELECT asset_id, tag_name, tag_path, unit, source_domain, is_mapped, "
        "  live_value, live_value_str, quality, live_at, sdt_compressed, compression_ratio "
        "FROM mapped_rows "
        "UNION ALL "
        "SELECT asset_id, tag_name, tag_path, unit, source_domain, is_mapped, "
        "  live_value, live_value_str, quality, live_at, sdt_compressed, compression_ratio "
        "FROM unmapped_rows "
        "WHERE :p_include_unmapped = true "
        "ORDER BY tag_name",
        [asset_id, minutes, asset_id, include_unmapped],
    )


def _hierarchy_asset_tag_summary(minutes: int = 60) -> tuple[str, list[Any]]:
    """Per-asset mapped/unmapped tag summary for hierarchy badges."""
    return (
        f"{_event_cte()}, "
        "latest_events AS ( "
        "  SELECT asset_id, tag_name, "
        "    ROW_NUMBER() OVER (PARTITION BY asset_id, tag_name ORDER BY event_timestamp DESC) AS rn "
        "  FROM events "
        "  WHERE event_timestamp >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP()) "
        "), event_tags AS ( "
        "  SELECT asset_id, tag_name FROM latest_events WHERE rn = 1 "
        "), mapped_tags AS ( "
        "  SELECT hierarchy_asset_id AS asset_id, normalized_tag_name AS tag_name "
        f"  FROM {_t('silver_signal_mapping_normalized')} "
        "  WHERE COALESCE(active, true) = true "
        "  GROUP BY hierarchy_asset_id, normalized_tag_name "
        "), mapped_counts AS ( "
        "  SELECT asset_id, COUNT(*) AS mapped_tag_count "
        "  FROM mapped_tags "
        "  GROUP BY asset_id "
        "), live_counts AS ( "
        "  SELECT asset_id, COUNT(*) AS live_tag_count "
        "  FROM event_tags "
        "  GROUP BY asset_id "
        "), mapped_live_counts AS ( "
        "  SELECT e.asset_id, COUNT(*) AS mapped_live_tag_count "
        "  FROM event_tags e "
        "  JOIN mapped_tags m ON e.asset_id = m.asset_id AND e.tag_name = m.tag_name "
        "  GROUP BY e.asset_id "
        "), unmapped_counts AS ( "
        "  SELECT e.asset_id, COUNT(*) AS unmapped_tag_count "
        "  FROM event_tags e "
        "  WHERE NOT EXISTS ("
        "    SELECT 1 FROM mapped_tags m "
        "    WHERE m.asset_id = e.asset_id AND m.tag_name = e.tag_name"
        "  ) "
        "  GROUP BY e.asset_id "
        ") "
        "SELECT h.asset_id, "
        "  COALESCE(mc.mapped_tag_count, 0) AS mapped_tag_count, "
        "  COALESCE(lc.live_tag_count, 0) AS live_tag_count, "
        "  COALESCE(mlc.mapped_live_tag_count, 0) AS mapped_live_tag_count, "
        "  COALESCE(uc.unmapped_tag_count, 0) AS unmapped_tag_count "
        f"FROM {_t('asset_hierarchy')} h "
        "LEFT JOIN mapped_counts mc ON h.asset_id = mc.asset_id "
        "LEFT JOIN live_counts lc ON h.asset_id = lc.asset_id "
        "LEFT JOIN mapped_live_counts mlc ON h.asset_id = mlc.asset_id "
        "LEFT JOIN unmapped_counts uc ON h.asset_id = uc.asset_id "
        "WHERE h.active = true "
        "ORDER BY h.asset_id",
        [minutes],
    )


def _hierarchy_child_aggregation(
    asset_id: str, minutes: int = 10,
) -> tuple[str, list[Any]]:
    """Aggregate latest tag values across all direct children of an asset.

    For each tag_name that appears across child assets, returns AVG/MIN/MAX
    of the most recent value per child. Useful for site-level roll-ups like
    "average SoC across all BESS units".
    """
    return (
        f"{_event_cte()}, "
        "child_ids AS ( "
        "  SELECT asset_id "
        f"  FROM {_t('asset_hierarchy')} "
        "  WHERE parent_asset_id = :p_asset_id AND active = true "
        "), recent AS ( "
        "  SELECT e.asset_id, e.tag_name, e.tag_value, "
        "    ROW_NUMBER() OVER (PARTITION BY e.asset_id, e.tag_name ORDER BY e.event_timestamp DESC) AS rn "
        "  FROM events e "
        "  JOIN child_ids c ON e.asset_id = c.asset_id "
        "  WHERE e.event_timestamp >= TIMESTAMPADD(MINUTE, -:p_minutes, CURRENT_TIMESTAMP()) "
        "    AND e.tag_value IS NOT NULL "
        ") "
        "SELECT tag_name, "
        "  ROUND(AVG(tag_value), 2) AS avg_value, "
        "  ROUND(MIN(tag_value), 2) AS min_value, "
        "  ROUND(MAX(tag_value), 2) AS max_value, "
        "  COUNT(DISTINCT asset_id) AS asset_count "
        "FROM recent "
        "WHERE rn = 1 "
        "GROUP BY tag_name "
        "HAVING COUNT(DISTINCT asset_id) > 1 "
        "ORDER BY tag_name",
        [asset_id, minutes],
    )


def _diagnostic() -> tuple[str, list[Any]]:
    """Quick health check: row counts and time range of raw_tags."""
    return (
        "SELECT"
        "  COUNT(*) AS total_rows,"
        "  COUNT(*) FILTER ("
        "    WHERE TIMESTAMP_MICROS(event_time) >= TIMESTAMPADD(MINUTE, -10, CURRENT_TIMESTAMP())"
        "  ) AS rows_last_10_min,"
        "  COUNT(*) FILTER ("
        "    WHERE ingestion_timestamp IS NOT NULL AND event_time IS NOT NULL"
        "      AND ingestion_timestamp < event_time"
        "  ) AS negative_latency_rows,"
        "  COUNT(*) FILTER ("
        "    WHERE event_time > UNIX_MICROS(TIMESTAMPADD(MINUTE, 5, CURRENT_TIMESTAMP()))"
        "  ) AS future_event_rows,"
        "  CAST(MIN(TIMESTAMP_MICROS(event_time)) AS STRING) AS oldest_event,"
        "  CAST(MAX(TIMESTAMP_MICROS(event_time)) AS STRING) AS newest_event,"
        "  CAST(CURRENT_TIMESTAMP() AS STRING) AS warehouse_now"
        f" FROM {_t('raw_tags')}",
        [],
    )


def _bom_current_conditions() -> tuple[str, list[Any]]:
    """Current weather conditions per BOM station."""
    return (
        "SELECT station_name, air_temp_c, apparent_temp_c, "
        "relative_humidity_pct, wind_speed_kmh, wind_direction, "
        "rainfall_mm, observation_timestamp "
        f"FROM {_t('bom_current_conditions')} "
        "ORDER BY station_name",
        [],
    )


def _bom_daily_summary() -> tuple[str, list[Any]]:
    """Daily weather summary per BOM station."""
    return (
        "SELECT station_name, observation_date, min_temp_c, max_temp_c, "
        "avg_humidity_pct, max_gust_kmh, total_rainfall_mm, observation_count "
        f"FROM {_t('bom_station_daily_summary')} "
        "ORDER BY observation_date DESC, station_name "
        "LIMIT 50",
        [],
    )


def _nem_market_snapshot() -> tuple[str, list[Any]]:
    """Latest NEM market snapshot per region."""
    return (
        "SELECT region_id, price_timestamp, rrp, "
        "total_demand_mw, available_generation_mw, net_interchange_mw "
        f"FROM {_t('nem_market_snapshot')} "
        "ORDER BY region_id",
        [],
    )


def _nem_dispatch_prices_history(hours: int = 6) -> tuple[str, list[Any]]:
    """Recent NEM dispatch prices for all regions."""
    return (
        "SELECT dispatch_timestamp, region_id, rrp "
        f"FROM {_t('nem_dispatch_prices')} "
        "WHERE dispatch_timestamp >= TIMESTAMPADD(HOUR, -:p_hours, CURRENT_TIMESTAMP()) "
        "ORDER BY dispatch_timestamp DESC",
        [hours],
    )


# === Time Travel / Historical Replay queries ===


def _asset_tags_range(
    asset_id: str,
    from_ts: str,
    to_ts: str,
    resolution: str | None = None,
    tags: list[str] | None = None,
) -> tuple[str, list[Any]]:
    """Tag history for an asset between from_ts and to_ts with optional downsampling.

    Auto-selects resolution from the time span when resolution is None:
      <= 1h   -> raw (capped at 10,000 rows)
      <= 6h   -> 1-minute averages
      <= 24h  -> 5-minute averages
      <= 7d   -> 15-minute averages
      <= 30d  -> 1-hour averages
    """
    from datetime import datetime  # noqa: PLC0415

    if resolution is None:
        try:
            dt_from = datetime.fromisoformat(from_ts.replace("Z", "+00:00"))
            dt_to = datetime.fromisoformat(to_ts.replace("Z", "+00:00"))
            span_hours = (dt_to - dt_from).total_seconds() / 3600
        except ValueError:
            span_hours = 1.0
        if span_hours <= 1:
            resolution = "raw"
        elif span_hours <= 6:
            resolution = "1m"
        elif span_hours <= 24:
            resolution = "5m"
        elif span_hours <= 168:
            resolution = "15m"
        else:
            resolution = "1h"

    tag_filter = ""
    tag_params: list[Any] = []
    if tags:
        placeholders = ", ".join([f":p_tag_{i}" for i in range(len(tags))])
        tag_filter = f" AND tag_name IN ({placeholders})"
        tag_params = list(tags)

    if resolution == "raw":
        return (
            f"{_event_cte()} "
            "SELECT event_timestamp, tag_name, tag_value, quality, sdt_compressed "
            "FROM events "
            "WHERE asset_id = :p_asset_id "
            f"AND event_timestamp >= :p_from AND event_timestamp <= :p_to{tag_filter} "
            "ORDER BY event_timestamp "
            "LIMIT 10000",
            [asset_id, from_ts, to_ts, *tag_params],
        )

    if resolution == "1m":
        bucket_expr = "DATE_TRUNC('minute', event_timestamp)"
    elif resolution == "5m":
        bucket_expr = "TIMESTAMP_SECONDS(FLOOR(UNIX_TIMESTAMP(event_timestamp) / 300) * 300)"
    elif resolution == "15m":
        bucket_expr = "TIMESTAMP_SECONDS(FLOOR(UNIX_TIMESTAMP(event_timestamp) / 900) * 900)"
    else:  # 1h
        bucket_expr = "DATE_TRUNC('hour', event_timestamp)"

    return (
        f"{_event_cte()}, "
        "bucketed AS ("
        f"  SELECT {bucket_expr} AS bucket, tag_name, "
        "  AVG(tag_value) AS tag_value, MAX(quality) AS quality, "
        "  BOOL_OR(sdt_compressed) AS sdt_compressed "
        "  FROM events "
        "  WHERE asset_id = :p_asset_id "
        f"  AND event_timestamp >= :p_from AND event_timestamp <= :p_to{tag_filter} "
        "  GROUP BY 1, 2"
        ") "
        "SELECT bucket AS event_timestamp, tag_name, tag_value, quality, sdt_compressed "
        "FROM bucketed "
        "ORDER BY event_timestamp",
        [asset_id, from_ts, to_ts, *tag_params],
    )


def _fleet_snapshot(timestamp: str) -> tuple[str, list[Any]]:
    """Point-in-time fleet health — latest score per asset at or before the requested timestamp.

    Reads from health_score_history (append-only streaming table) which accumulates
    a row per asset per pipeline refresh. QUALIFY ROW_NUMBER picks the most recent
    score at or before the requested timestamp.
    """
    return (
        "SELECT scored_at, asset_id, health_score, primary_risk_tag, "
        "risk_description, anomaly_tags, estimated_hours_to_failure "
        f"FROM {_t('health_score_history')} "
        "WHERE scored_at <= :p_timestamp "
        "QUALIFY ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY scored_at DESC) = 1 "
        "ORDER BY health_score ASC",
        [timestamp],
    )


def _asset_tags_export(
    asset_id: str,
    from_ts: str,
    to_ts: str,
) -> tuple[str, list[Any]]:
    """All tag events for CSV export — no downsampling, row-count checked by caller."""
    return (
        f"{_event_cte()} "
        "SELECT event_timestamp, tag_name, tag_value, quality, sdt_compressed "
        "FROM events "
        "WHERE asset_id = :p_asset_id "
        "AND event_timestamp >= :p_from AND event_timestamp <= :p_to "
        "ORDER BY event_timestamp",
        [asset_id, from_ts, to_ts],
    )


def _asset_forensics(
    asset_id: str,
    event_time: str,
    window_minutes: int = 30,
) -> tuple[str, list[Any]]:
    """Raw tag events for ±window_minutes around an event timestamp."""
    return (
        f"{_event_cte()} "
        "SELECT event_timestamp, tag_name, tag_value, quality, sdt_compressed "
        "FROM events "
        "WHERE asset_id = :p_asset_id "
        "AND event_timestamp >= TIMESTAMPADD(MINUTE, -:p_window, CAST(:p_event_time AS TIMESTAMP)) "
        "AND event_timestamp <= TIMESTAMPADD(MINUTE, :p_window2, CAST(:p_event_time2 AS TIMESTAMP)) "
        "ORDER BY event_timestamp",
        [asset_id, window_minutes, event_time, window_minutes, event_time],
    )


QUERY_BUILDERS: dict[str, Any] = {
    "diagnostic": _diagnostic,
    "throughput": _throughput,
    "latency": _latency,
    "latencyE2e": _latency_e2e,
    "compression": _compression,
    "eventsLatest": _events_latest,
    "assets": _assets,
    "assetById": _asset_by_id,
    "assetTags": _asset_tags,
    "compressionComparison": _compression_comparison,
    "rawTagsStorageMetrics": _raw_tags_storage_metrics,
    "rawTagsTotalCount": _raw_tags_total_count,
    "sdtConfig": _sdt_config,
    "sdtConfigUpdate": _sdt_config_update,
    # Analytics queries (APP-PRD)
    "healthScores": _health_scores,
    "revenueRisk": _revenue_risk,
    "nemPrices": _nem_prices,
    "priceForecast": _price_forecast,
    "revenueSummary": _revenue_summary,
    # Databricks 101: BOM + NEMWEB live data
    "bomCurrentConditions": _bom_current_conditions,
    "bomDailySummary": _bom_daily_summary,
    "nemMarketSnapshot": _nem_market_snapshot,
    "nemDispatchPricesHistory": _nem_dispatch_prices_history,
    # Asset Framework queries
    "hierarchy": _hierarchy,
    "hierarchyAsset": _hierarchy_asset,
    "hierarchyCreate": _hierarchy_create,
    "hierarchyUpdate": _hierarchy_update,
    "hierarchyDelete": _hierarchy_delete,
    "hierarchyMove": _hierarchy_move,
    "templatesList": _templates_list,
    "templateById": _template_by_id,
    "templateAssets": _template_assets,
    "templateCreate": _template_create,
    "templateUpdate": _template_update,
    "templateDelete": _template_delete,
    "templateAttrCreate": _template_attr_create,
    "templateAttrUpdate": _template_attr_update,
    "templateAttrDelete": _template_attr_delete,
    "applyTemplate": _apply_template,
    "assetAttrValues": _asset_attr_values,
    "assetAttrValuesUpdate": _asset_attr_values_update,
    "assetLiveAttrValues": _asset_live_attr_values,
    "hierarchyAssetTags": _hierarchy_asset_tags,
    "hierarchyAssetTagSummary": _hierarchy_asset_tag_summary,
    "hierarchyChildAggregation": _hierarchy_child_aggregation,
    # Time Travel / Historical Replay
    "assetTagsRange": _asset_tags_range,
    "fleetSnapshot": _fleet_snapshot,
    "assetTagsExport": _asset_tags_export,
    "assetForensics": _asset_forensics,
}


def build_query(name: str, **kwargs: Any) -> tuple[str, list[Any]]:
    builder = QUERY_BUILDERS.get(name)
    if builder is None:
        raise ValueError(f"Unknown query: {name}")
    return builder(**kwargs)


def _get_client() -> WorkspaceClient:
    global _client, _warehouse_id
    if _client is None:
        _client = WorkspaceClient()
        _warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
    return _client


async def execute(name: str, **kwargs: Any) -> list[dict[str, Any]]:
    """Execute a named query via the Databricks SDK Statement Execution API."""
    sql, params = build_query(name, **kwargs)

    # Map positional params to named :p_xxx placeholders found in the SQL.
    # Must include type_ so the API knows how to bind (e.g. LIMIT needs INT).
    sdk_params: list[StatementParameterListItem] | None = None
    if params:
        param_names = re.findall(r":(\w+)", sql)
        sdk_params = []
        for i, pname in enumerate(param_names):
            val = params[i] if i < len(params) else None
            if isinstance(val, bool):
                type_str = "BOOLEAN"
            elif isinstance(val, int):
                type_str = "INT"
            elif isinstance(val, float):
                type_str = "DOUBLE"
            else:
                type_str = "STRING"
            sdk_params.append(
                StatementParameterListItem(
                    name=pname,
                    value=str(val) if val is not None else None,
                    type=type_str,
                )
            )

    client = _get_client()
    try:
        # Run blocking SDK call in thread pool so the event loop stays responsive
        # and the app proxy does not 502 due to timeout while waiting for SQL.
        response = await asyncio.to_thread(
            client.statement_execution.execute_statement,
            warehouse_id=_warehouse_id,
            catalog=_catalog,
            schema=_schema,
            statement=sql,
            parameters=sdk_params,
            wait_timeout="30s",
        )
    except Exception as exc:
        _logger.exception("SQL execution failed for query %s", name)
        raise QueryError(name, str(exc)) from exc

    if response.status and response.status.state != StatementState.SUCCEEDED:
        err_msg = response.status.error.message if response.status.error else "unknown"
        _logger.error("Query %s failed: %s", name, err_msg)
        raise QueryError(name, err_msg)

    if not response.manifest or not response.result or not response.result.data_array:
        return []

    # Extract column names and types for proper type conversion
    # type_name is an enum (ColumnInfoTypeName), use .value to get string like "INT"
    schema_cols = response.manifest.schema.columns
    columns = [col.name for col in schema_cols]
    col_types = [
        col.type_name.value if hasattr(col.type_name, "value") else str(col.type_name)
        for col in schema_cols
    ]

    def convert_value(val: Any, type_name: str) -> Any:
        """Convert string values from data_array to proper Python types."""
        if val is None:
            return None
        if type_name == "BOOLEAN":
            return val.lower() == "true" if isinstance(val, str) else bool(val)
        if type_name in ("INT", "BIGINT", "SMALLINT", "TINYINT"):
            return int(val) if val else None
        if type_name in ("DOUBLE", "FLOAT", "DECIMAL"):
            return float(val) if val else None
        return val  # STRING, TIMESTAMP, etc. - keep as-is

    results = []
    for row in response.result.data_array:
        converted_row = [convert_value(val, col_types[i]) for i, val in enumerate(row)]
        results.append(dict(zip(columns, converted_row)))
    return results
