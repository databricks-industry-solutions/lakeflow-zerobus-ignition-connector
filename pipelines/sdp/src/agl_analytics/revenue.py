"""Revenue-at-risk computation module.

Implements FR-202 from APP-PRD.md: Revenue-at-risk calculation and action recommendations.
"""

from collections import defaultdict


def compute_trip_probability(health_score: float) -> float:
    """Compute trip probability from health score.

    trip_probability = 1.0 - health_score, clamped to [0.0, 1.0].

    Args:
        health_score: Asset health score (0.0 to 1.0)

    Returns:
        Trip probability (0.0 to 1.0)
    """
    trip_prob = 1.0 - health_score
    return max(0.0, min(1.0, trip_prob))


def compute_revenue_at_risk(
    capacity_mw: float,
    window_hours: float,
    forecast_price_aud_mwh: float,
    trip_probability: float,
) -> float:
    """Compute revenue at risk for an asset during a high-price window.

    Formula: capacity_mw * window_hours * forecast_price_aud_mwh * trip_probability

    Args:
        capacity_mw: Asset rated capacity in MW
        window_hours: Duration of the high-price window in hours
        forecast_price_aud_mwh: Expected price during window ($/MWh)
        trip_probability: Probability of asset tripping offline (0.0 to 1.0)

    Returns:
        Revenue at risk in AUD
    """
    return capacity_mw * window_hours * forecast_price_aud_mwh * trip_probability


def recommend_action(health_score: float, window_start: str) -> str:
    """Generate recommended action based on health score.

    Rule-based recommendations per APP-PRD.md FR-109:
    - health > 0.8: "Monitor - no action needed"
    - health 0.5-0.8: "Schedule inspection before {window_start}"
    - health 0.3-0.5: "Urgent: schedule maintenance tonight"
    - health < 0.3: "Critical: consider preemptive shutdown and repair to protect fleet"

    Args:
        health_score: Asset health score (0.0 to 1.0)
        window_start: Start time of the high-price window (for inspection message)

    Returns:
        Human-readable action recommendation string
    """
    if health_score > 0.8:
        return "Monitor - no action needed"
    elif health_score > 0.5:
        return f"Schedule inspection before {window_start}"
    elif health_score > 0.3:
        return "Urgent: schedule maintenance tonight"
    else:
        return "Critical: consider preemptive shutdown and repair to protect fleet"


def compute_fleet_summary(asset_risks: list[dict]) -> dict:
    """Compute fleet-level revenue at risk aggregations.

    Args:
        asset_risks: List of dicts with keys: asset_id, site, asset_type, revenue_at_risk_aud

    Returns:
        Dict with:
        - total_revenue_at_risk: Sum of all asset risks
        - assets_at_risk_count: Count of assets with risk > 0
        - by_site: Dict mapping site name to total risk
        - by_asset_type: Dict mapping asset type to total risk
    """
    if not asset_risks:
        return {
            "total_revenue_at_risk": 0.0,
            "assets_at_risk_count": 0,
            "by_site": {},
            "by_asset_type": {},
        }

    total = 0.0
    by_site: dict[str, float] = defaultdict(float)
    by_asset_type: dict[str, float] = defaultdict(float)

    for asset in asset_risks:
        risk = asset.get("revenue_at_risk_aud", 0.0)
        total += risk
        by_site[asset["site"]] += risk
        by_asset_type[asset["asset_type"]] += risk

    return {
        "total_revenue_at_risk": total,
        "assets_at_risk_count": len(asset_risks),
        "by_site": dict(by_site),
        "by_asset_type": dict(by_asset_type),
    }
