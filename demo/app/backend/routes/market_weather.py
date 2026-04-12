"""Market & Weather routes for Databricks 101 demo: BOM weather + NEMWEB market data."""

import time

from fastapi import APIRouter, Query

from ..services import query as query_service
from .helpers import wrap as _wrap

router = APIRouter(prefix="/api/market-weather")


@router.get("/bom/current")
async def get_bom_current() -> dict:
    """Get current weather conditions from BOM stations."""
    start = time.monotonic()
    data = await query_service.execute("bomCurrentConditions")
    return _wrap(data, start)


@router.get("/bom/daily")
async def get_bom_daily() -> dict:
    """Get daily weather summary from BOM stations."""
    start = time.monotonic()
    data = await query_service.execute("bomDailySummary")
    return _wrap(data, start)


@router.get("/nem/snapshot")
async def get_nem_snapshot() -> dict:
    """Get latest NEM market snapshot per region."""
    start = time.monotonic()
    data = await query_service.execute("nemMarketSnapshot")
    return _wrap(data, start)


@router.get("/nem/prices")
async def get_nem_prices_history(hours: int = Query(default=6, ge=1, le=72)) -> dict:
    """Get NEM dispatch price history for the last N hours."""
    start = time.monotonic()
    data = await query_service.execute("nemDispatchPricesHistory", hours=hours)
    return _wrap(data, start)
