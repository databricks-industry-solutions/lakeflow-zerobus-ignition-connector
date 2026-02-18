"""Query service for PostgreSQL (Databricks Lakebase).

Provides direct asyncpg access to Lakebase PostgreSQL for low-latency OLTP reads.
Used alongside the DBSQL query service to demonstrate the different read paths.

Environment variables:
- LAKEBASE_HOST: PostgreSQL host (e.g., ep-xxx.databricks.com)
- LAKEBASE_PORT: PostgreSQL port (default 5432)
- LAKEBASE_DATABASE: Database name
- LAKEBASE_USER: Role name
- LAKEBASE_PASSWORD: Password
- LAKEBASE_TABLE: Table name (default raw_tags)
"""

from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import urlparse
from typing import Any

_logger = logging.getLogger(__name__)

# Configuration from environment
_host: str = os.environ.get("LAKEBASE_HOST", "")
_port: int = int(os.environ.get("LAKEBASE_PORT", "5432"))
_database: str = os.environ.get("LAKEBASE_DATABASE", "")
_user: str = os.environ.get("LAKEBASE_USER", "")
_password: str = os.environ.get("LAKEBASE_PASSWORD", "")
_table: str = os.environ.get("LAKEBASE_TABLE", "raw_tags")
_resource: str = os.environ.get("LAKEBASE_RESOURCE", "")


def _apply_resource_overrides() -> None:
    """Best-effort parsing for app resource values.

    Databricks app resources can surface either host-like values or full Postgres URLs.
    If a URL is provided, we use embedded components as defaults.
    """
    global _host, _port, _database, _user, _password
    if not _resource:
        return

    # If resource is a URL, parse as DSN-like input.
    if "://" in _resource:
        parsed = urlparse(_resource)
        if parsed.hostname and not _host:
            _host = parsed.hostname
        if parsed.port and (_port == 5432):
            _port = parsed.port
        if parsed.path and parsed.path != "/" and not _database:
            _database = parsed.path.lstrip("/")
        if parsed.username and not _user:
            _user = parsed.username
        if parsed.password and not _password:
            _password = parsed.password
        return

    # Otherwise treat resource as hostname.
    if not _host:
        _host = _resource.strip()


_apply_resource_overrides()

# Connection pool (lazily initialized)
_pool = None


def is_configured() -> bool:
    """Check if Lakebase environment variables are set."""
    return bool(_host and _database and _user and _password)


async def get_pool():
    """Get or create the asyncpg connection pool."""
    global _pool
    if _pool is None:
        try:
            import asyncpg
            _pool = await asyncpg.create_pool(
                host=_host,
                port=_port,
                database=_database,
                user=_user,
                password=_password,
                min_size=2,
                max_size=10,
                ssl="require",
                command_timeout=30,
            )
            _logger.info("PostgreSQL connection pool created: %s:%s/%s", _host, _port, _database)
        except Exception as e:
            _logger.error("Failed to create PostgreSQL connection pool: %s", e)
            raise
    return _pool


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        _logger.info("PostgreSQL connection pool closed")


async def execute(sql: str, *args: Any) -> list[dict[str, Any]]:
    """Execute a SQL query and return results as a list of dicts."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
        return [dict(row) for row in rows]


async def execute_one(sql: str, *args: Any) -> dict[str, Any] | None:
    """Execute a SQL query and return a single row as dict, or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *args)
        return dict(row) if row else None


# Metric window size (seconds)
METRIC_WINDOW_SECONDS = 5


async def get_throughput(minutes: int = 5) -> list[dict[str, Any]]:
    """Get throughput metrics in 5-second windows."""
    sql = f"""
        SELECT
            to_timestamp(floor(event_time / 5000000.0) * 5) AS window_start,
            to_timestamp(floor(event_time / 5000000.0) * 5 + 5) AS window_end,
            CAST(ROUND(COUNT(*) * GREATEST(1.0, COALESCE(AVG(compression_ratio), 0))) AS BIGINT) AS records_raw,
            COUNT(*) AS records_after_sdt,
            COUNT(*) * 100 AS bytes_estimate,
            AVG((ingestion_timestamp - event_time)::float / 1000.0) AS avg_latency_ms,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY (ingestion_timestamp - event_time)::float / 1000.0) AS p99_latency_ms,
            COUNT(DISTINCT tag_path) AS tags_active,
            AVG(COALESCE(compression_ratio, 0)) AS sdt_compression_ratio,
            FALSE AS sdt_enabled
        FROM {_table}
        WHERE to_timestamp(event_time / 1000000.0) >= NOW() - INTERVAL '{minutes * 2} minutes'
          AND event_time IS NOT NULL
          AND ingestion_timestamp IS NOT NULL
          AND event_time <= EXTRACT(EPOCH FROM (NOW() + INTERVAL '5 minutes')) * 1000000
          AND (ingestion_timestamp - event_time) BETWEEN 0 AND 3600000000
        GROUP BY 1, 2
        HAVING to_timestamp(floor(event_time / 5000000.0) * 5) >= NOW() - INTERVAL '{minutes} minutes'
        ORDER BY window_start
    """
    return await execute(sql)


async def get_latency(minutes: int = 5) -> list[dict[str, Any]]:
    """Get latency metrics in 5-second windows."""
    sql = f"""
        SELECT
            to_timestamp(floor(event_time / 5000000.0) * 5) AS window_start,
            to_timestamp(floor(event_time / 5000000.0) * 5 + 5) AS window_end,
            AVG((ingestion_timestamp - event_time)::float / 1000.0) AS avg_latency_ms,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY (ingestion_timestamp - event_time)::float / 1000.0) AS p99_latency_ms
        FROM {_table}
        WHERE to_timestamp(event_time / 1000000.0) >= NOW() - INTERVAL '{minutes * 2} minutes'
          AND event_time IS NOT NULL
          AND ingestion_timestamp IS NOT NULL
          AND event_time <= EXTRACT(EPOCH FROM (NOW() + INTERVAL '5 minutes')) * 1000000
          AND (ingestion_timestamp - event_time) BETWEEN 0 AND 3600000000
        GROUP BY 1, 2
        HAVING to_timestamp(floor(event_time / 5000000.0) * 5) >= NOW() - INTERVAL '{minutes} minutes'
        ORDER BY window_start
    """
    return await execute(sql)


async def get_events_latest(limit: int = 50) -> list[dict[str, Any]]:
    """Get the most recent events."""
    sql = f"""
        SELECT
            to_timestamp(event_time / 1000000.0) AS event_timestamp,
            to_timestamp(ingestion_timestamp / 1000000.0) AS ingest_timestamp,
            tag_path,
            tag_provider,
            CASE
                WHEN tag_path LIKE '%%/%%/%%/%%/%%/%%/%%'
                THEN LOWER(SPLIT_PART(REGEXP_REPLACE(tag_path, '^\[.*?\]', ''), '/', 4) || '_' || SPLIT_PART(REGEXP_REPLACE(tag_path, '^\[.*?\]', ''), '/', 6))
                ELSE COALESCE(LOWER(tag_provider), 'unknown')
            END AS asset_id,
            COALESCE(tag_provider, 'unknown') AS asset_type,
            CASE
                WHEN tag_path LIKE '%%/%%' THEN LOWER(SPLIT_PART(tag_path, '/', -1))
                ELSE LOWER(tag_path)
            END AS tag_name,
            numeric_value AS tag_value,
            quality_code AS quality,
            COALESCE(sdt_compressed, false) AS sdt_compressed,
            COALESCE(compression_ratio, 0.0) AS compression_ratio
        FROM {_table}
        ORDER BY ingestion_timestamp DESC
        LIMIT $1
    """
    return await execute(sql, limit)


async def get_diagnostic() -> dict[str, Any]:
    """Get diagnostic information about the table."""
    sql = f"""
        SELECT
            COUNT(*) AS total_rows,
            COUNT(*) FILTER (WHERE to_timestamp(event_time / 1000000.0) >= NOW() - INTERVAL '10 minutes') AS rows_last_10_min,
            COUNT(*) FILTER (WHERE ingestion_timestamp IS NOT NULL AND event_time IS NOT NULL AND ingestion_timestamp < event_time) AS negative_latency_rows,
            COUNT(*) FILTER (
                WHERE event_time > EXTRACT(EPOCH FROM (NOW() + INTERVAL '5 minutes')) * 1000000
            ) AS future_event_rows,
            MIN(to_timestamp(event_time / 1000000.0))::text AS oldest_event,
            MAX(to_timestamp(event_time / 1000000.0))::text AS newest_event,
            NOW()::text AS db_now
        FROM {_table}
    """
    result = await execute_one(sql)
    return result or {
        "total_rows": 0,
        "rows_last_10_min": 0,
        "oldest_event": None,
        "newest_event": None,
        "db_now": None,
    }


async def check_health() -> dict[str, Any]:
    """Check connection health."""
    if not is_configured():
        return {
            "status": "not_configured",
            "message": "Lakebase environment variables not set",
        }

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            if result == 1:
                return {
                    "status": "healthy",
                    "host": _host,
                    "database": _database,
                    "table": _table,
                    "pool_size": pool.get_size(),
                    "pool_free": pool.get_idle_size(),
                }
    except Exception as e:
        _logger.error("PostgreSQL health check failed: %s", e)
        return {
            "status": "unhealthy",
            "error": str(e),
        }

    return {"status": "unknown"}
