import time
from typing import Literal

from fastapi import APIRouter, Query

from ..services import query as query_service
from ..services.query import QueryError
from .helpers import wrap as _wrap

router = APIRouter(prefix="/api/metrics")

MetricsSource = Literal["raw_tags", "raw_throughput"]


@router.get("/throughput")
async def throughput(
    source: MetricsSource = Query("raw_tags", description="raw_tags (landing) or raw_throughput (deduped)"),
    minutes: int = Query(default=5, ge=1, le=1440, description="Lookback window in minutes"),
) -> dict:
    start = time.monotonic()
    try:
        data = await query_service.execute("throughput", minutes=minutes, source=source)
    except QueryError as exc:
        return _wrap([], start, source, error=exc.message)
    return _wrap(data, start, source)


@router.get("/latency")
async def latency(
    source: MetricsSource = Query("raw_tags", description="raw_tags (landing) or raw_throughput (deduped)"),
    minutes: int = Query(default=5, ge=1, le=1440, description="Lookback window in minutes"),
) -> dict:
    start = time.monotonic()
    try:
        connector = await query_service.execute("latency", minutes=minutes, source=source)
    except QueryError as exc:
        return _wrap([], start, source, error=exc.message)
    # Merge E2E latency from raw_throughput (CDF _commit_timestamp) when available
    try:
        e2e = await query_service.execute("latencyE2e", minutes=minutes)
        by_window = {r["window_start"]: r for r in connector}
        for r in e2e:
            key = r["window_start"]
            if key in by_window:
                by_window[key]["avg_e2e_latency_ms"] = r.get("avg_e2e_latency_ms")
                by_window[key]["p99_e2e_latency_ms"] = r.get("p99_e2e_latency_ms")
                by_window[key]["avg_delta_to_app_ms"] = r.get("avg_delta_to_app_ms")
                by_window[key]["p99_delta_to_app_ms"] = r.get("p99_delta_to_app_ms")
        data = list(by_window.values())
        data.sort(key=lambda x: x["window_start"])
    except Exception:
        data = connector
    return _wrap(data, start, source)


@router.get("/compression")
async def compression() -> dict:
    start = time.monotonic()
    try:
        data = await query_service.execute("compression")
    except QueryError as exc:
        return _wrap([], start, error=exc.message)
    return _wrap(data, start)


@router.get("/diagnostic")
async def diagnostic() -> dict:
    """Quick health check: row counts and time range of raw_tags.

    Helps diagnose why the dashboard may be empty (e.g. all data older than
    the 5-minute window, wrong catalog/schema, or permission errors).
    """
    start = time.monotonic()
    try:
        rows = await query_service.execute("diagnostic")
    except QueryError as exc:
        return _wrap([], start, error=exc.message)
    data = rows[0] if rows else {}
    return _wrap(data, start)
