"""Analytics routes for APP-PRD: health scores and revenue-at-risk."""

import time

from fastapi import APIRouter, Query

from ..services import query as query_service
from .helpers import wrap as _wrap

router = APIRouter(prefix="/api/analytics")


@router.get("/health-scores")
async def get_health_scores() -> dict:
    """Get health scores for all assets, sorted by risk (lowest health first)."""
    start = time.monotonic()
    data = await query_service.execute("healthScores")
    return _wrap(data, start)


@router.get("/revenue-risk")
async def get_revenue_risk() -> dict:
    """Get revenue at risk per asset for upcoming high-price windows."""
    start = time.monotonic()
    data = await query_service.execute("revenueRisk")
    return _wrap(data, start)


@router.get("/revenue-summary")
async def get_revenue_summary() -> dict:
    """Get aggregate revenue risk summary."""
    start = time.monotonic()
    data = await query_service.execute("revenueSummary")
    if data:
        return _wrap(data[0], start)
    return _wrap(
        {
            "assets_at_risk": 0,
            "total_revenue_at_risk_aud": 0.0,
            "avg_health_score": 1.0,
            "next_risk_window": None,
        },
        start,
    )


@router.get("/nem-prices")
async def get_nem_prices(hours: int = Query(default=24, ge=1, le=168)) -> dict:
    """Get NEM dispatch prices for the last N hours."""
    start = time.monotonic()
    data = await query_service.execute("nemPrices", hours=hours)
    return _wrap(data, start)


@router.get("/price-forecast")
async def get_price_forecast() -> dict:
    """Get 48-hour price forecast."""
    start = time.monotonic()
    data = await query_service.execute("priceForecast")
    return _wrap(data, start)
