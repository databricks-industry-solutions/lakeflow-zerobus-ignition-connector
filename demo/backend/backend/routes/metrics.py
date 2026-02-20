import time
from typing import Literal

from fastapi import APIRouter, Query

from ..services import query as query_service

router = APIRouter(prefix="/api/metrics")

MetricsSource = Literal["raw_tags", "raw_throughput"]


def _wrap(data: object, start: float, source: str | None = None) -> dict:
    from datetime import datetime, timezone
    meta: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_time_ms": round((time.monotonic() - start) * 1000),
    }
    if source:
        meta["source"] = source
    return {"data": data, "meta": meta}


@router.get("/throughput")
async def throughput(
    source: MetricsSource = Query("raw_tags"),
    minutes: int = Query(default=5, ge=1, le=1440),
) -> dict:
    start = time.monotonic()
    data = await query_service.execute("throughput", minutes=minutes)
    return _wrap(data, start, source)


@router.get("/latency")
async def latency(
    source: MetricsSource = Query("raw_tags"),
    minutes: int = Query(default=5, ge=1, le=1440),
) -> dict:
    start = time.monotonic()
    data = await query_service.execute("latency", minutes=minutes)
    return _wrap(data, start, source)


@router.get("/compression")
async def compression() -> dict:
    start = time.monotonic()
    data = await query_service.execute("compression")
    return _wrap(data, start)


@router.get("/diagnostic")
async def diagnostic() -> dict:
    start = time.monotonic()
    data = await query_service.execute("diagnostic")
    row = data[0] if data else {}
    return _wrap(row, start)
