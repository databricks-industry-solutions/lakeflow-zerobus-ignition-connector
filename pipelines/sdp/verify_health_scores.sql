-- Verify health_scores MV (run in Databricks SQL or via verify_ml_health.py).
-- Replace __CATALOG__ and __SCHEMA__ when running via script.
-- Success: rows exist (z-score path on enriched_tags).
SELECT scored_at, asset_id, health_score, primary_risk_tag, risk_description, anomaly_tags, estimated_hours_to_failure
FROM __CATALOG__.__SCHEMA__.health_scores
ORDER BY scored_at DESC
LIMIT 20;
