"""Synthetic NEM price generation module.

Implements FR-203 from APP-PRD.md: Generate realistic NEM price patterns for demo.
"""

import random
from datetime import datetime, timedelta


def generate_price_forecast(hours: int = 48, region: str = "NSW1") -> list[dict]:
    """Generate synthetic 48-hour NEM price forecast.

    Creates 5-minute interval forecasts with:
    - Base pattern: overnight $30-80, morning ramp, afternoon peak $200-500
    - 2-3 spike events per 24h during peak hours (4-7pm), prices $2,000-$15,000
    - At least one spike within next 24 hours (demo urgency)

    Args:
        hours: Number of hours to forecast (default 48)
        region: NEM region code (default NSW1)

    Returns:
        List of dicts with: target_interval, region, forecast_price_aud_mwh, confidence
    """
    intervals_per_hour = 12  # 5-minute intervals
    total_intervals = hours * intervals_per_hour

    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    forecast = []

    # Ensure at least one spike in first 24h and 1-2 more in second 24h
    spike_intervals: set[int] = set()

    # First spike: somewhere in hours 12-20 (afternoon/evening of day 1)
    first_spike_hour = random.randint(12, 20)
    first_spike_start = first_spike_hour * intervals_per_hour
    for i in range(first_spike_start, min(first_spike_start + 12, 288)):  # ~1 hour spike
        spike_intervals.add(i)

    # Second spike: hours 36-44 (afternoon of day 2) if we have 48h
    if hours >= 48:
        second_spike_hour = random.randint(36, 44)
        second_spike_start = second_spike_hour * intervals_per_hour
        for i in range(second_spike_start, min(second_spike_start + 18, total_intervals)):
            spike_intervals.add(i)

    for i in range(total_intervals):
        interval_time = now + timedelta(minutes=i * 5)
        hour = interval_time.hour

        # Base price pattern by time of day
        if 22 <= hour or hour < 5:
            # Overnight: low prices $30-80
            base_price = random.uniform(30, 80)
            confidence = "high"
        elif 5 <= hour < 8:
            # Morning ramp: $60-150
            base_price = random.uniform(60, 150)
            confidence = "high"
        elif 8 <= hour < 16:
            # Daytime: moderate $80-200
            base_price = random.uniform(80, 200)
            confidence = "medium"
        elif 16 <= hour < 20:
            # Peak hours: $150-500
            base_price = random.uniform(150, 500)
            confidence = "medium"
        else:
            # Evening decline: $80-200
            base_price = random.uniform(80, 200)
            confidence = "medium"

        # Apply spike if this interval is marked
        if i in spike_intervals:
            base_price = random.uniform(2000, 15000)
            confidence = "low"  # High uncertainty for spikes

        forecast.append(
            {
                "target_interval": interval_time,
                "region": region,
                "forecast_price_aud_mwh": round(base_price, 2),
                "confidence": confidence,
            }
        )

    return forecast


def generate_historical_prices(days: int = 30, region: str = "NSW1") -> list[dict]:
    """Generate synthetic historical NEM dispatch prices.

    Creates 5-minute interval prices following realistic NEM patterns.

    Args:
        days: Number of days of history (default 30)
        region: NEM region code (default NSW1)

    Returns:
        List of dicts with: interval_start, interval_end, region, price_aud_mwh, demand_mw
    """
    intervals_per_day = 288  # 24h * 12 intervals/hour
    total_intervals = days * intervals_per_day

    # Start from midnight N days ago
    end_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(days=days)

    prices = []
    for i in range(total_intervals):
        interval_start = start_time + timedelta(minutes=i * 5)
        interval_end = interval_start + timedelta(minutes=5)
        hour = interval_start.hour

        # Base price pattern (similar to forecast but without guaranteed spikes)
        if 22 <= hour or hour < 5:
            base_price = random.uniform(30, 80)
            base_demand = random.uniform(6000, 8000)
        elif 5 <= hour < 8:
            base_price = random.uniform(60, 150)
            base_demand = random.uniform(8000, 10000)
        elif 8 <= hour < 16:
            base_price = random.uniform(80, 200)
            base_demand = random.uniform(10000, 12000)
        elif 16 <= hour < 20:
            base_price = random.uniform(150, 500)
            base_demand = random.uniform(12000, 14000)
        else:
            base_price = random.uniform(80, 200)
            base_demand = random.uniform(10000, 12000)

        # Random spikes (~2% chance during peak hours)
        if 16 <= hour < 20 and random.random() < 0.02:
            base_price = random.uniform(1000, 10000)
            base_demand = random.uniform(13000, 15000)

        prices.append(
            {
                "interval_start": interval_start,
                "interval_end": interval_end,
                "region": region,
                "price_aud_mwh": round(base_price, 2),
                "demand_mw": round(base_demand, 1),
            }
        )

    return prices


def find_high_price_windows(forecast: list[dict], threshold: float = 300.0) -> list[dict]:
    """Identify contiguous high-price windows in a forecast.

    Args:
        forecast: List of forecast records with target_interval and forecast_price_aud_mwh
        threshold: Price threshold for "high price" (default $300/MWh)

    Returns:
        List of window dicts with: window_start, window_end, avg_price, peak_price, duration_hours
    """
    if not forecast:
        return []

    windows = []
    current_window: list[dict] | None = None

    for record in forecast:
        price = record["forecast_price_aud_mwh"]

        if price > threshold:
            if current_window is None:
                current_window = []
            current_window.append(record)
        else:
            # End of high-price window
            if current_window:
                windows.append(_summarize_window(current_window))
                current_window = None

    # Handle window at end of forecast
    if current_window:
        windows.append(_summarize_window(current_window))

    return windows


def _summarize_window(records: list[dict]) -> dict:
    """Summarize a contiguous high-price window."""
    prices = [r["forecast_price_aud_mwh"] for r in records]
    window_start = records[0]["target_interval"]
    window_end = records[-1]["target_interval"] + timedelta(minutes=5)
    duration = (window_end - window_start).total_seconds() / 3600

    return {
        "window_start": window_start,
        "window_end": window_end,
        "avg_price": sum(prices) / len(prices),
        "peak_price": max(prices),
        "duration_hours": duration,
    }
