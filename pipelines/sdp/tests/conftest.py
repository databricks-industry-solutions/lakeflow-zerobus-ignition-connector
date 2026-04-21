"""Shared pytest fixtures for agl_analytics tests."""

import pytest


@pytest.fixture
def sample_wind_asset() -> dict:
    """Sample wind turbine asset for testing."""
    return {
        "asset_id": "wind_hexham_t01",
        "site": "Hexham",
        "asset_type": "wind_turbine",
        "capacity_mw": 12.0,
        "region": "NSW1",
    }


@pytest.fixture
def sample_battery_asset() -> dict:
    """Sample battery asset for testing."""
    return {
        "asset_id": "bess_liddell_b01",
        "site": "Liddell Battery",
        "asset_type": "battery",
        "capacity_mw": 25.0,
        "region": "NSW1",
    }


@pytest.fixture
def sample_tag_values_normal() -> dict[str, float]:
    """Sample tag values within normal range."""
    return {
        "nacelle/temperature_c": 68.0,  # Normal range: 62-74
        "generator/power_kw": 8500.0,
        "grid/frequency_hz": 50.0,
        "rotor/wind_speed_ms": 12.0,
    }


@pytest.fixture
def sample_tag_values_anomalous() -> dict[str, float]:
    """Sample tag values with anomalies."""
    return {
        "nacelle/temperature_c": 87.0,  # Anomalous: well above 74
        "generator/power_kw": 8500.0,
        "grid/frequency_hz": 50.0,
        "rotor/wind_speed_ms": 12.0,
    }


@pytest.fixture
def sample_tag_stats() -> dict[str, dict]:
    """Sample rolling statistics for tags (mean, stddev)."""
    return {
        "nacelle/temperature_c": {"mean": 68.0, "stddev": 3.0},
        "generator/power_kw": {"mean": 8000.0, "stddev": 500.0},
        "grid/frequency_hz": {"mean": 50.0, "stddev": 0.05},
        "rotor/wind_speed_ms": {"mean": 10.0, "stddev": 2.0},
    }
