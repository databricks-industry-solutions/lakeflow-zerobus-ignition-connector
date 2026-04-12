"""Tests for schema definitions matching APP-PRD.md table specifications."""

from dataclasses import fields

from agl_analytics.schemas import (
    HealthScoreRecord,
    NemPriceRecord,
    PriceForecastRecord,
    RevenueRiskRecord,
)


def test_nem_price_schema_fields():
    """NemPriceRecord has all APP-PRD columns for agl_demo.market.nem_prices."""
    field_names = {f.name for f in fields(NemPriceRecord)}
    expected = {"interval_start", "interval_end", "region", "price_aud_mwh", "demand_mw"}
    assert field_names == expected


def test_price_forecast_schema_fields():
    """PriceForecastRecord has all APP-PRD columns for agl_demo.market.price_forecast."""
    field_names = {f.name for f in fields(PriceForecastRecord)}
    expected = {"forecast_timestamp", "target_interval", "region", "forecast_price_aud_mwh", "confidence"}
    assert field_names == expected


def test_health_score_schema_fields():
    """HealthScoreRecord has all APP-PRD columns for agl_demo.analytics.health_scores."""
    field_names = {f.name for f in fields(HealthScoreRecord)}
    expected = {
        "scored_at",
        "asset_id",
        "health_score",
        "primary_risk_tag",
        "risk_description",
        "anomaly_tags",
        "estimated_hours_to_failure",
    }
    assert field_names == expected


def test_revenue_risk_schema_fields():
    """RevenueRiskRecord has all APP-PRD columns for agl_demo.analytics.revenue_risk."""
    field_names = {f.name for f in fields(RevenueRiskRecord)}
    expected = {
        "computed_at",
        "asset_id",
        "risk_window_start",
        "risk_window_end",
        "forecast_price_aud_mwh",
        "asset_capacity_mw",
        "health_score",
        "trip_probability",
        "revenue_at_risk_aud",
        "recommended_action",
    }
    assert field_names == expected
