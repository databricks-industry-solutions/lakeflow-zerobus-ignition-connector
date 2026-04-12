"""Schema definitions for AGL analytics tables.

These dataclasses match the table schemas defined in APP-PRD.md:
- agl_demo.market.nem_prices
- agl_demo.market.price_forecast
- agl_demo.analytics.health_scores
- agl_demo.analytics.revenue_risk
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class NemPriceRecord:
    """Schema for agl_demo.market.nem_prices - 5-minute NEM dispatch prices."""

    interval_start: datetime
    interval_end: datetime
    region: str
    price_aud_mwh: float
    demand_mw: float


@dataclass
class PriceForecastRecord:
    """Schema for agl_demo.market.price_forecast - 48-hour price forecast."""

    forecast_timestamp: datetime
    target_interval: datetime
    region: str
    forecast_price_aud_mwh: float
    confidence: str  # "high", "medium", "low"


@dataclass
class HealthScoreRecord:
    """Schema for agl_demo.analytics.health_scores - per-asset health scores."""

    scored_at: datetime
    asset_id: str
    health_score: float  # 0.0 (critical) to 1.0 (healthy)
    primary_risk_tag: str  # Tag driving the risk
    risk_description: str  # Human-readable risk summary
    anomaly_tags: list[str]  # All tags currently anomalous
    estimated_hours_to_failure: float | None  # Nullable


@dataclass
class RevenueRiskRecord:
    """Schema for agl_demo.analytics.revenue_risk - revenue at risk per asset."""

    computed_at: datetime
    asset_id: str
    risk_window_start: datetime
    risk_window_end: datetime
    forecast_price_aud_mwh: float
    asset_capacity_mw: float
    health_score: float
    trip_probability: float  # 0.0 to 1.0
    revenue_at_risk_aud: float
    recommended_action: str
