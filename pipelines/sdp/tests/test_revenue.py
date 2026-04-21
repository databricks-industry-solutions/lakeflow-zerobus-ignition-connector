"""Tests for revenue-at-risk computation module."""

import pytest

from agl_analytics.revenue import (
    compute_fleet_summary,
    compute_revenue_at_risk,
    compute_trip_probability,
    recommend_action,
)


class TestTripProbability:
    """Tests for trip probability computation."""

    def test_trip_probability_from_health(self):
        """trip_prob = 1 - health_score."""
        assert compute_trip_probability(0.8) == pytest.approx(0.2)
        assert compute_trip_probability(0.5) == pytest.approx(0.5)
        assert compute_trip_probability(1.0) == pytest.approx(0.0)

    def test_trip_probability_clamped_high(self):
        """health_score > 1.0 clamps to trip_prob 0.0."""
        assert compute_trip_probability(1.5) == 0.0

    def test_trip_probability_clamped_low(self):
        """health_score < 0.0 clamps to trip_prob 1.0."""
        assert compute_trip_probability(-0.5) == 1.0


class TestRevenueAtRisk:
    """Tests for revenue at risk calculation."""

    def test_revenue_at_risk_formula(self):
        """25 MW * 2 hours * $8000/MWh * 0.7 = $280,000."""
        revenue = compute_revenue_at_risk(
            capacity_mw=25.0,
            window_hours=2.0,
            forecast_price_aud_mwh=8000.0,
            trip_probability=0.7,
        )
        assert revenue == pytest.approx(280_000.0)

    def test_revenue_at_risk_zero_probability(self):
        """Healthy asset (trip_prob=0) has $0 risk."""
        revenue = compute_revenue_at_risk(
            capacity_mw=25.0,
            window_hours=2.0,
            forecast_price_aud_mwh=8000.0,
            trip_probability=0.0,
        )
        assert revenue == 0.0

    def test_revenue_at_risk_full_probability(self):
        """Critical asset (trip_prob=1) has full revenue at risk."""
        revenue = compute_revenue_at_risk(
            capacity_mw=12.0,
            window_hours=3.0,
            forecast_price_aud_mwh=5000.0,
            trip_probability=1.0,
        )
        # 12 * 3 * 5000 * 1.0 = 180,000
        assert revenue == pytest.approx(180_000.0)


class TestRecommendedAction:
    """Tests for action recommendation based on health score."""

    def test_recommended_action_healthy(self):
        """health 0.9 -> 'Monitor'."""
        action = recommend_action(health_score=0.9, window_start="2026-02-13 16:00")
        assert "Monitor" in action
        assert "no action" in action.lower()

    def test_recommended_action_warning(self):
        """health 0.6 -> 'Schedule inspection'."""
        action = recommend_action(health_score=0.6, window_start="2026-02-13 16:00")
        assert "Schedule inspection" in action
        assert "2026-02-13 16:00" in action

    def test_recommended_action_urgent(self):
        """health 0.4 -> 'Urgent'."""
        action = recommend_action(health_score=0.4, window_start="2026-02-13 16:00")
        assert "Urgent" in action
        assert "maintenance tonight" in action.lower()

    def test_recommended_action_critical(self):
        """health 0.2 -> 'Critical'."""
        action = recommend_action(health_score=0.2, window_start="2026-02-13 16:00")
        assert "Critical" in action
        assert "shutdown" in action.lower() or "repair" in action.lower()


class TestFleetSummary:
    """Tests for fleet-level aggregation."""

    def test_fleet_summary_totals(self):
        """Aggregates revenue_at_risk across 3 assets."""
        asset_risks = [
            {
                "asset_id": "wind_hexham_t01",
                "site": "Hexham",
                "asset_type": "wind_turbine",
                "revenue_at_risk_aud": 100_000.0,
            },
            {
                "asset_id": "wind_hexham_t02",
                "site": "Hexham",
                "asset_type": "wind_turbine",
                "revenue_at_risk_aud": 50_000.0,
            },
            {
                "asset_id": "bess_liddell_b01",
                "site": "Liddell Battery",
                "asset_type": "battery",
                "revenue_at_risk_aud": 200_000.0,
            },
        ]
        summary = compute_fleet_summary(asset_risks)

        assert summary["total_revenue_at_risk"] == pytest.approx(350_000.0)
        assert summary["assets_at_risk_count"] == 3

    def test_fleet_summary_by_site(self):
        """Aggregates by site."""
        asset_risks = [
            {"asset_id": "a1", "site": "Hexham", "asset_type": "wind", "revenue_at_risk_aud": 100_000.0},
            {"asset_id": "a2", "site": "Hexham", "asset_type": "wind", "revenue_at_risk_aud": 50_000.0},
            {"asset_id": "a3", "site": "Liddell", "asset_type": "battery", "revenue_at_risk_aud": 200_000.0},
        ]
        summary = compute_fleet_summary(asset_risks)

        assert summary["by_site"]["Hexham"] == pytest.approx(150_000.0)
        assert summary["by_site"]["Liddell"] == pytest.approx(200_000.0)

    def test_fleet_summary_by_asset_type(self):
        """Aggregates by asset type."""
        asset_risks = [
            {"asset_id": "a1", "site": "S1", "asset_type": "wind_turbine", "revenue_at_risk_aud": 100_000.0},
            {"asset_id": "a2", "site": "S2", "asset_type": "wind_turbine", "revenue_at_risk_aud": 50_000.0},
            {"asset_id": "a3", "site": "S3", "asset_type": "battery", "revenue_at_risk_aud": 200_000.0},
        ]
        summary = compute_fleet_summary(asset_risks)

        assert summary["by_asset_type"]["wind_turbine"] == pytest.approx(150_000.0)
        assert summary["by_asset_type"]["battery"] == pytest.approx(200_000.0)

    def test_fleet_summary_empty(self):
        """Empty list returns zero totals."""
        summary = compute_fleet_summary([])
        assert summary["total_revenue_at_risk"] == 0.0
        assert summary["assets_at_risk_count"] == 0
        assert summary["by_site"] == {}
        assert summary["by_asset_type"] == {}
