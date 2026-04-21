"""Train and register an IsolationForest anomaly detection model for asset health.

Runs as a Databricks notebook/job. Generates synthetic "normal" tag data,
trains sklearn IsolationForest, logs to MLflow Unity Catalog model registry.

Constants (MODEL_NAME, FEATURE_COLS, SIGNAL_RANGES) are imported from
agl_analytics.health to keep a single source of truth shared with the
SDP pipeline scoring code.
"""

import os

import mlflow
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# Keep local constants in this job script so training does not depend on
# installing project wheels on ephemeral job clusters.
MODEL_NAME = "ot_demo.ot.asset_health_model"

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
FEATURE_COLS = sorted(SIGNAL_RANGES.keys())

mlflow.set_registry_uri("databricks-uc")

EXPERIMENT_NAME = os.environ.get(
    "MLFLOW_EXPERIMENT_NAME",
    "/Users/david.okeeffe@databricks.com/zerobus-health-model",
)


def generate_normal_training_data(n_samples: int = 5000) -> pd.DataFrame:
    """Generate synthetic normal operating data for training."""
    np.random.seed(42)
    data = {}
    for signal, (lo, hi) in SIGNAL_RANGES.items():
        mean = (lo + hi) / 2
        std = (hi - lo) / 6  # ~99.7% within range
        data[signal] = np.random.normal(mean, std, n_samples)
    return pd.DataFrame(data)[FEATURE_COLS]


def main():
    mlflow.set_experiment(EXPERIMENT_NAME)

    # Generate training data (normal operations only)
    X_train = generate_normal_training_data(5000)

    with mlflow.start_run(run_name="isolation_forest_v1") as run:
        # Train
        model = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42,
        )
        model.fit(X_train)

        # Log params
        mlflow.log_param("n_estimators", 100)
        mlflow.log_param("contamination", 0.05)
        mlflow.log_param("n_features", len(FEATURE_COLS))
        mlflow.log_param("feature_columns", ",".join(FEATURE_COLS))
        mlflow.log_param("n_training_samples", len(X_train))

        # Log model with signature
        from mlflow.models.signature import infer_signature
        signature = infer_signature(X_train, model.decision_function(X_train))

        mlflow.sklearn.log_model(
            model,
            artifact_path="model",
            signature=signature,
            input_example=X_train.head(3),
            registered_model_name=MODEL_NAME,
        )

        # Log training data stats for reference
        stats = X_train.describe().to_dict()
        mlflow.log_dict(stats, "training_stats.json")

        print(f"Model registered: {MODEL_NAME}")
        print(f"Run ID: {run.info.run_id}")
        print(f"Features: {FEATURE_COLS}")


if __name__ == "__main__":
    main()
