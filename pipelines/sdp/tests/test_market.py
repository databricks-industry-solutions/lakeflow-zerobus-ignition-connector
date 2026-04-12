"""Tests for synthetic NEM price generation module."""

from agl_analytics.market import (
    find_high_price_windows,
    generate_historical_prices,
    generate_price_forecast,
)


class TestPriceForecast:
    """Tests for 48-hour price forecast generation."""

    def test_forecast_length_48h(self):
        """48 hours * 12 intervals/hr = 576 records."""
        forecast = generate_price_forecast(hours=48, region="NSW1")
        assert len(forecast) == 576

    def test_forecast_has_spike_events(self):
        """At least 2 intervals > $300/MWh."""
        forecast = generate_price_forecast(hours=48, region="NSW1")
        spikes = [r for r in forecast if r["forecast_price_aud_mwh"] > 300.0]
        assert len(spikes) >= 2

    def test_forecast_overnight_low(self):
        """Avg price 10pm-5am intervals should be < $100/MWh."""
        forecast = generate_price_forecast(hours=48, region="NSW1")
        # Check intervals where hour is between 22-23 or 0-5
        overnight = []
        for r in forecast:
            hour = r["target_interval"].hour
            if hour >= 22 or hour < 5:
                overnight.append(r["forecast_price_aud_mwh"])

        if overnight:
            avg_overnight = sum(overnight) / len(overnight)
            assert avg_overnight < 100.0

    def test_forecast_spike_in_next_24h(self):
        """At least one spike (>$300) within first 24 hours (288 intervals)."""
        forecast = generate_price_forecast(hours=48, region="NSW1")
        first_24h = forecast[:288]
        spikes = [r for r in first_24h if r["forecast_price_aud_mwh"] > 300.0]
        assert len(spikes) >= 1

    def test_forecast_record_structure(self):
        """Each record has required fields."""
        forecast = generate_price_forecast(hours=48, region="NSW1")
        record = forecast[0]
        assert "target_interval" in record
        assert "region" in record
        assert "forecast_price_aud_mwh" in record
        assert "confidence" in record
        assert record["region"] == "NSW1"


class TestHistoricalPrices:
    """Tests for historical price generation."""

    def test_historical_prices_30_days(self):
        """30 days * 288 intervals/day = 8640 records."""
        prices = generate_historical_prices(days=30, region="NSW1")
        assert len(prices) == 8640

    def test_historical_record_structure(self):
        """Each record has required fields."""
        prices = generate_historical_prices(days=1, region="NSW1")
        record = prices[0]
        assert "interval_start" in record
        assert "interval_end" in record
        assert "region" in record
        assert "price_aud_mwh" in record
        assert "demand_mw" in record


class TestHighPriceWindows:
    """Tests for high price window identification."""

    def test_find_high_price_windows(self):
        """Identifies correct windows from known forecast."""
        # Create a simple forecast with known pattern
        from datetime import datetime, timedelta

        base = datetime(2026, 2, 13, 0, 0)
        forecast = []
        for i in range(24):  # 2 hours of 5-min intervals
            price = 50.0  # Low price
            if 8 <= i < 14:  # 40-70 min: spike window
                price = 500.0
            forecast.append(
                {
                    "target_interval": base + timedelta(minutes=i * 5),
                    "forecast_price_aud_mwh": price,
                }
            )

        windows = find_high_price_windows(forecast, threshold=300.0)
        assert len(windows) == 1
        assert windows[0]["duration_hours"] > 0
        assert windows[0]["peak_price"] == 500.0

    def test_find_high_price_windows_none(self):
        """Returns empty list when no prices exceed threshold."""
        from datetime import datetime, timedelta

        base = datetime(2026, 2, 13, 0, 0)
        forecast = [
            {"target_interval": base + timedelta(minutes=i * 5), "forecast_price_aud_mwh": 50.0} for i in range(12)
        ]
        windows = find_high_price_windows(forecast, threshold=300.0)
        assert windows == []

    def test_find_high_price_windows_multiple(self):
        """Identifies multiple separate windows."""
        from datetime import datetime, timedelta

        base = datetime(2026, 2, 13, 0, 0)
        forecast = []
        for i in range(36):
            price = 50.0
            if 4 <= i < 8:  # First spike
                price = 400.0
            if 20 <= i < 24:  # Second spike (gap in between)
                price = 600.0
            forecast.append(
                {
                    "target_interval": base + timedelta(minutes=i * 5),
                    "forecast_price_aud_mwh": price,
                }
            )

        windows = find_high_price_windows(forecast, threshold=300.0)
        assert len(windows) == 2
