-- UC Python UDF: score_asset_health
-- Wraps the IsolationForest anomaly detection model from the UC registry as a
-- SQL-callable function.  Parameters are in sorted(SIGNAL_RANGES.keys()) order
-- to match the training feature vector.

CREATE OR REPLACE FUNCTION __CATALOG__.__SCHEMA__.score_asset_health(
  alarm_count DOUBLE,
  ambient_temp_c DOUBLE,
  bess_active_power_mw DOUBLE,
  max_rack_temp_c DOUBLE,
  net_power DOUBLE,
  poi_frequency_hz DOUBLE,
  poi_net_mw DOUBLE,
  poi_voltage_kv DOUBLE,
  power DOUBLE,
  soc DOUBLE,
  soc_pct DOUBLE,
  soh_pct DOUBLE,
  wind_speed DOUBLE
)
RETURNS DOUBLE
LANGUAGE PYTHON
COMMENT 'Score asset health using IsolationForest anomaly detection model from UC registry'
AS $$
  import mlflow
  import numpy as np
  model = mlflow.sklearn.load_model("models:/agl_demo.ot.asset_health_model/latest")
  X = np.array([[alarm_count, ambient_temp_c, bess_active_power_mw, max_rack_temp_c,
                 net_power, poi_frequency_hz, poi_net_mw, poi_voltage_kv,
                 power, soc, soc_pct, soh_pct, wind_speed]])
  raw = model.decision_function(X)[0]
  score = 1.0 / (1.0 + np.exp(-raw * 2))
  return float(max(0.0, min(1.0, score)))
$$;

-- Grant execute to the service principal
GRANT EXECUTE ON FUNCTION __CATALOG__.__SCHEMA__.score_asset_health TO `__SP_APPLICATION_ID__`;
