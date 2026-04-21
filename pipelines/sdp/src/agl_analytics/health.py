"""Health scoring module - z-score and ML-based anomaly detection.

Implements FR-201 from APP-PRD.md: Z-score based anomaly detection per asset,
with optional IsolationForest ML model blending when a trained model is available.
"""

import logging
import math

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ML model constants (single source of truth - also used by train_health_model)
# ---------------------------------------------------------------------------

MODEL_NAME = "ot_demo.ot.asset_health_model"

# Key signals and their normal operating ranges (used for training + fill values)
SIGNAL_RANGES = {
    "soc_pct": (20.0, 95.0),
    "soh_pct": (85.0, 100.0),
    "bess_active_power_mw": (-500.0, 500.0),
    "ambient_temp_c": (10.0, 42.0),
    "max_rack_temp_c": (18.0, 38.0),
    "poi_net_mw": (-500.0, 500.0),
    "poi_frequency_hz": (49.85, 50.15),
    "poi_voltage_kv": (60.0, 70.0),
    "alarm_count": (0.0, 3.0),
    "wind_speed": (2.0, 25.0),
    "power": (0.0, 5000.0),
    "soc": (15.0, 95.0),
    "net_power": (-200.0, 200.0),
}

# Feature columns the model expects (sorted for consistency)
FEATURE_COLS = sorted(SIGNAL_RANGES.keys())

# Midpoint fill values for missing features (better than filling with 0)
SIGNAL_FILL_VALUES = {k: (lo + hi) / 2 for k, (lo, hi) in SIGNAL_RANGES.items()}


def load_health_model(model_name: str = MODEL_NAME):
    """Load the IsolationForest model from MLflow UC model registry.

    Uses mlflow.sklearn.load_model (not pyfunc) to get the raw sklearn model
    so we can call decision_function() for continuous anomaly scores.

    Args:
        model_name: Fully qualified UC model name (catalog.schema.model)

    Returns:
        Tuple of (model, feature_cols) on success, or (None, []) on failure.
    """
    try:
        import mlflow.sklearn
    except ImportError:
        log.info("mlflow not installed - ML model scoring disabled")
        return (None, [])

    try:
        model = mlflow.sklearn.load_model(f"models:/{model_name}/latest")
        log.info("Loaded ML model: %s", model_name)
        return (model, FEATURE_COLS)
    except Exception as exc:
        log.warning("ML model not available (%s): %s", model_name, exc)
        return (None, [])

# Key monitoring tags per asset type (from APP-PRD.md FR-105)
# These map to signal_name in silver_signal_mapping
# Include both mapping-style (short) and simulator path-style (e.g. subsystem/signal) names.
WIND_KEY_TAGS = [
    "nacelle/temperature_c",
    "generator/power_kw",
    "grid/frequency_hz",
    "rotor/wind_speed_ms",
]

# AGL BESS key tags (match silver_signal_mapping signal_name values)
# Also include simulator path-style names (demo/simulator profiles) so derived signal_name matches.
BATTERY_KEY_TAGS = [
    "max_rack_temp_c",       # Battery rack temperature
    "soc_pct",               # State of charge
    "ambient_temp_c",        # Ambient temperature
    "bess_active_power_mw",  # Active power output
    # Simulator profile (battery-bess.json) path-style names
    "battery/soc_pct",
    "battery/temperature_c",
    "thermal/ambient_temp_c",
    "inverter/power_kw",
    # AGL Fleet simulator [agl_bess] style (lowercased from enriched_tags derivation)
    "telemetry/soc_pct",
    "telemetry/activepower_mw",
    "thermal/maxracktemp_c",
    "thermal/ambienttemp_c",
]


def compute_zscore(value: float, mean: float, stddev: float) -> float:
    """Compute z-score for a value given mean and standard deviation.

    Args:
        value: Current value to score
        mean: Rolling mean for the tag
        stddev: Rolling standard deviation for the tag

    Returns:
        Z-score. Returns 0.0 if stddev is 0 to avoid division by zero.
    """
    if math.isclose(stddev, 0.0, abs_tol=1e-12):
        return 0.0
    return (value - mean) / stddev


def is_anomalous(zscore: float, threshold: float = 2.0) -> bool:
    """Check if a z-score indicates an anomaly.

    Args:
        zscore: The z-score to check
        threshold: Threshold for anomaly detection (default 2.0 = 2 sigma)

    Returns:
        True if abs(zscore) > threshold, indicating anomaly.
    """
    return abs(zscore) > threshold


def compute_health_score(anomalous_count: int, total_tag_count: int) -> float:
    """Compute health score based on anomalous tag ratio.

    Health score = 1.0 - (anomalous_count / total_tag_count), clamped to [0.0, 1.0].

    Args:
        anomalous_count: Number of tags currently anomalous
        total_tag_count: Total number of key tags being monitored

    Returns:
        Health score from 0.0 (critical) to 1.0 (healthy).
    """
    if total_tag_count == 0:
        return 1.0
    ratio = anomalous_count / total_tag_count
    score = 1.0 - ratio
    return max(0.0, min(1.0, score))


def identify_primary_risk_tag(tag_zscores: dict[str, float]) -> tuple[str, float]:
    """Identify the tag with the highest absolute z-score deviation.

    Args:
        tag_zscores: Dictionary mapping tag names to their z-scores

    Returns:
        Tuple of (tag_name, zscore) for the tag with highest abs(zscore).
        Returns ("", 0.0) if dict is empty.
    """
    if not tag_zscores:
        return ("", 0.0)

    primary_tag = max(tag_zscores.keys(), key=lambda t: abs(tag_zscores[t]))
    return (primary_tag, tag_zscores[primary_tag])


def generate_risk_description(
    primary_tag: str,
    zscore: float,
    current_value: float,
    expected_range: tuple[float, float],
) -> str:
    """Generate a human-readable risk description.

    Args:
        primary_tag: Name of the tag driving the risk
        zscore: Z-score of the primary tag
        current_value: Current value of the tag
        expected_range: Tuple of (min, max) expected values

    Returns:
        Human-readable description string.
    """
    direction = "above" if zscore > 0 else "below"
    return (
        f"Primary risk: {primary_tag} at {current_value:.1f} "
        f"(expected {expected_range[0]:.0f}-{expected_range[1]:.0f}, "
        f"z-score: {zscore:.1f}, {direction} normal range)"
    )


def get_key_tags(asset_type: str) -> list[str]:
    """Get the key monitoring tags for an asset type.

    Args:
        asset_type: Type of asset ("wind_turbine" or "battery")

    Returns:
        List of key tag names to monitor for this asset type.
        Returns empty list for unknown asset types.
    """
    if asset_type == "wind_turbine":
        return WIND_KEY_TAGS.copy()
    elif asset_type == "battery":
        return BATTERY_KEY_TAGS.copy()
    return []
