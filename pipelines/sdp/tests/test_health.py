"""Tests for health scoring module - z-score anomaly detection."""

import pytest

from agl_analytics.health import (
    compute_health_score,
    compute_zscore,
    generate_risk_description,
    get_key_tags,
    identify_primary_risk_tag,
    is_anomalous,
)


class TestZscore:
    """Tests for z-score computation."""

    def test_zscore_normal_value(self):
        """Value within 1 stddev returns abs(zscore) < 2."""
        # value=68, mean=68, stddev=3 -> zscore = 0
        zscore = compute_zscore(value=68.0, mean=68.0, stddev=3.0)
        assert abs(zscore) < 2.0

        # value=70, mean=68, stddev=3 -> zscore = 0.67
        zscore = compute_zscore(value=70.0, mean=68.0, stddev=3.0)
        assert abs(zscore) < 2.0

    def test_zscore_anomalous_value(self):
        """Value > 2 stddev from mean returns abs(zscore) > 2."""
        # value=87, mean=68, stddev=3 -> zscore = 6.33
        zscore = compute_zscore(value=87.0, mean=68.0, stddev=3.0)
        assert abs(zscore) > 2.0

    def test_zscore_zero_stddev(self):
        """stddev=0 returns zscore=0.0 (no division by zero)."""
        zscore = compute_zscore(value=100.0, mean=50.0, stddev=0.0)
        assert zscore == 0.0


class TestIsAnomalous:
    """Tests for anomaly detection threshold."""

    def test_is_anomalous_true(self):
        """Z-score above threshold is anomalous."""
        assert is_anomalous(2.5) is True
        assert is_anomalous(-2.5) is True

    def test_is_anomalous_false(self):
        """Z-score below threshold is not anomalous."""
        assert is_anomalous(1.5) is False
        assert is_anomalous(-1.5) is False

    def test_is_anomalous_custom_threshold(self):
        """Custom threshold works."""
        assert is_anomalous(1.5, threshold=1.0) is True
        assert is_anomalous(2.5, threshold=3.0) is False


class TestHealthScore:
    """Tests for health score computation."""

    def test_health_score_all_healthy(self):
        """0 anomalous tags, 6 total -> 1.0."""
        score = compute_health_score(anomalous_count=0, total_tag_count=6)
        assert score == 1.0

    def test_health_score_all_anomalous(self):
        """6 anomalous, 6 total -> 0.0."""
        score = compute_health_score(anomalous_count=6, total_tag_count=6)
        assert score == 0.0

    def test_health_score_partial(self):
        """2 anomalous, 6 total -> approx 0.667."""
        score = compute_health_score(anomalous_count=2, total_tag_count=6)
        assert score == pytest.approx(0.667, rel=0.01)

    def test_health_score_clamped_high(self):
        """Score clamped to 1.0 max."""
        score = compute_health_score(anomalous_count=-1, total_tag_count=6)
        assert score == 1.0

    def test_health_score_clamped_low(self):
        """Score clamped to 0.0 min."""
        score = compute_health_score(anomalous_count=10, total_tag_count=6)
        assert score == 0.0


class TestPrimaryRiskTag:
    """Tests for identifying primary risk tag."""

    def test_primary_risk_tag_highest_zscore(self):
        """Tag with highest abs(zscore) is selected."""
        tag_zscores = {
            "nacelle/temperature_c": 3.2,
            "generator/power_kw": 0.5,
            "grid/frequency_hz": -1.8,
            "rotor/wind_speed_ms": 1.2,
        }
        tag, zscore = identify_primary_risk_tag(tag_zscores)
        assert tag == "nacelle/temperature_c"
        assert zscore == 3.2

    def test_primary_risk_tag_negative_zscore(self):
        """Negative z-score with highest absolute value is selected."""
        tag_zscores = {
            "nacelle/temperature_c": 1.5,
            "grid/frequency_hz": -4.0,
        }
        tag, zscore = identify_primary_risk_tag(tag_zscores)
        assert tag == "grid/frequency_hz"
        assert zscore == -4.0


class TestRiskDescription:
    """Tests for risk description generation."""

    def test_generate_risk_description(self):
        """Generates human-readable risk description."""
        desc = generate_risk_description(
            primary_tag="nacelle/temperature_c",
            zscore=3.2,
            current_value=87.0,
            expected_range=(62.0, 74.0),
        )
        assert "nacelle/temperature_c" in desc
        assert "87" in desc
        assert "62" in desc or "74" in desc


class TestKeyTags:
    """Tests for key monitoring tags per asset type."""

    def test_key_tags_wind(self):
        """Wind asset type returns 4 expected monitoring tags."""
        tags = get_key_tags("wind_turbine")
        assert len(tags) == 4
        assert "nacelle/temperature_c" in tags
        assert "generator/power_kw" in tags
        assert "grid/frequency_hz" in tags
        assert "rotor/wind_speed_ms" in tags

    def test_key_tags_battery(self):
        """Battery asset type returns expected AGL BESS monitoring tags (mapping + simulator styles)."""
        tags = get_key_tags("battery")
        assert len(tags) == 12
        # Signal mapping style (from silver_signal_mapping)
        assert "max_rack_temp_c" in tags
        assert "soc_pct" in tags
        assert "ambient_temp_c" in tags
        assert "bess_active_power_mw" in tags
        # Simulator [sim] style
        assert "battery/soc_pct" in tags
        assert "battery/temperature_c" in tags
        # AGL Fleet simulator [agl_bess] style (lowercased)
        assert "telemetry/soc_pct" in tags
        assert "telemetry/activepower_mw" in tags
        assert "thermal/maxracktemp_c" in tags
        assert "thermal/ambienttemp_c" in tags

    def test_key_tags_unknown_type(self):
        """Unknown asset type returns empty list."""
        tags = get_key_tags("unknown")
        assert tags == []
