"""PostgreSQL (Lakebase) metrics routes.

Provides direct PostgreSQL read path for low-latency OLTP queries.
Isolated from the DBSQL metrics to demonstrate dual data paths.
"""

import time

from fastapi import APIRouter, Query

from ..services import postgres_query
from .helpers import wrap as _wrap_base

router = APIRouter(prefix="/api/postgres-metrics")


def _wrap(data: object, start: float, error: str | None = None) -> dict:
    """Wrap response with lakebase source tag."""
    return _wrap_base(data, start, source="lakebase", error=error)


@router.get("/health")
async def health() -> dict:
    """Check PostgreSQL connection health."""
    start = time.monotonic()
    try:
        result = await postgres_query.check_health()
        return _wrap(result, start)
    except Exception as exc:
        return _wrap(None, start, error=str(exc))


@router.get("/throughput")
async def throughput(
    minutes: int = Query(default=5, ge=1, le=1440, description="Lookback window in minutes"),
) -> dict:
    """Get throughput metrics from PostgreSQL."""
    start = time.monotonic()

    if not postgres_query.is_configured():
        return _wrap([], start, error="Lakebase not configured")

    try:
        data = await postgres_query.get_throughput(minutes=minutes)
        # Convert datetime objects to ISO strings for JSON serialization
        for row in data:
            if row.get("window_start"):
                row["window_start"] = row["window_start"].isoformat() if hasattr(row["window_start"], "isoformat") else str(row["window_start"])
            if row.get("window_end"):
                row["window_end"] = row["window_end"].isoformat() if hasattr(row["window_end"], "isoformat") else str(row["window_end"])
        return _wrap(data, start)
    except Exception as exc:
        return _wrap([], start, error=str(exc))


@router.get("/latency")
async def latency(
    minutes: int = Query(default=5, ge=1, le=1440, description="Lookback window in minutes"),
) -> dict:
    """Get latency metrics from PostgreSQL."""
    start = time.monotonic()

    if not postgres_query.is_configured():
        return _wrap([], start, error="Lakebase not configured")

    try:
        data = await postgres_query.get_latency(minutes=minutes)
        # Convert datetime objects to ISO strings
        for row in data:
            if row.get("window_start"):
                row["window_start"] = row["window_start"].isoformat() if hasattr(row["window_start"], "isoformat") else str(row["window_start"])
            if row.get("window_end"):
                row["window_end"] = row["window_end"].isoformat() if hasattr(row["window_end"], "isoformat") else str(row["window_end"])
        return _wrap(data, start)
    except Exception as exc:
        return _wrap([], start, error=str(exc))


@router.get("/events/latest")
async def events_latest(
    limit: int = Query(default=50, ge=1, le=500, description="Number of events to return"),
) -> dict:
    """Get latest events from PostgreSQL."""
    start = time.monotonic()

    if not postgres_query.is_configured():
        return _wrap([], start, error="Lakebase not configured")

    try:
        data = await postgres_query.get_events_latest(limit=limit)
        # Convert datetime objects to ISO strings
        for row in data:
            if row.get("event_timestamp"):
                row["event_timestamp"] = row["event_timestamp"].isoformat() if hasattr(row["event_timestamp"], "isoformat") else str(row["event_timestamp"])
            if row.get("ingest_timestamp"):
                row["ingest_timestamp"] = row["ingest_timestamp"].isoformat() if hasattr(row["ingest_timestamp"], "isoformat") else str(row["ingest_timestamp"])
        return _wrap(data, start)
    except Exception as exc:
        return _wrap([], start, error=str(exc))


@router.get("/diagnostic")
async def diagnostic() -> dict:
    """Get diagnostic information about the PostgreSQL table."""
    start = time.monotonic()

    if not postgres_query.is_configured():
        return _wrap(
            {
                "configured": False,
                "message": "Lakebase environment variables not set (LAKEBASE_HOST, LAKEBASE_DATABASE, LAKEBASE_USER, LAKEBASE_PASSWORD)",
            },
            start,
        )

    try:
        data = await postgres_query.get_diagnostic()
        data["configured"] = True
        return _wrap(data, start)
    except Exception as exc:
        return _wrap({"configured": True, "error": str(exc)}, start, error=str(exc))
