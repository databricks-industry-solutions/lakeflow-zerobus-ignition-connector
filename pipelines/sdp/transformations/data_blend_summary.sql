-- Data Blend Summary: SQL transformations in the same Lakeflow pipeline.
--
-- Demonstrates that Python and SQL coexist in a single pipeline:
--   Python: fetches external APIs, complex joins, ML scoring
--   SQL:    declarative aggregations, business logic, self-documenting
--
-- These views read from Python-created tables and produce business-level
-- summaries combining OT, weather, and market context.


-- ═══════════════════════════════════════════════════════════════════════════
-- VIEW 1: Per-asset operational summary with weather + market context
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REFRESH MATERIALIZED VIEW operational_summary_by_asset
(
  CONSTRAINT has_asset EXPECT (asset_id IS NOT NULL),
  CONSTRAINT has_window EXPECT (latest_window IS NOT NULL),
  CONSTRAINT positive_samples EXPECT (total_samples > 0)
)
COMMENT 'Gold: per-asset operational summary with weather and market context. Built in SQL, reading from Python-created tables. Demonstrates multi-language pipelines.'
AS
SELECT
  asset_id,
  MAX(window_5min)                                    AS latest_window,
  COUNT(DISTINCT signal_name)                         AS signal_count,
  SUM(sample_count)                                   AS total_samples,

  -- OT metrics
  ROUND(AVG(avg_value), 2)                            AS mean_signal_value,
  ROUND(MIN(min_value), 2)                            AS overall_min,
  ROUND(MAX(max_value), 2)                            AS overall_max,

  -- Weather context
  FIRST(weather_station)                              AS weather_station,
  ROUND(AVG(air_temp_c), 1)                           AS avg_temp_c,
  ROUND(AVG(wind_speed_kmh), 0)                       AS avg_wind_kmh,
  ROUND(AVG(relative_humidity_pct), 0)                AS avg_humidity_pct,

  -- Market context
  FIRST(nem_region)                                   AS nem_region,
  ROUND(AVG(spot_price_aud_mwh), 2)                   AS avg_spot_price,
  ROUND(MAX(spot_price_aud_mwh), 2)                   AS peak_spot_price,
  ROUND(MIN(spot_price_aud_mwh), 2)                   AS min_spot_price

FROM blended_operational_context
GROUP BY asset_id;


-- ═══════════════════════════════════════════════════════════════════════════
-- VIEW 2: Fleet market risk summary (health scores + spot prices)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REFRESH MATERIALIZED VIEW fleet_market_risk_summary
(
  CONSTRAINT has_asset EXPECT (asset_id IS NOT NULL),
  CONSTRAINT has_health EXPECT (health_score IS NOT NULL),
  CONSTRAINT has_price EXPECT (spot_price_aud_mwh IS NOT NULL)
)
COMMENT 'Gold: fleet-level risk view joining asset health scores with NEM spot prices. Flags assets at risk during high-price intervals. SQL reading from Python tables.'
AS
SELECT
  h.asset_id,
  h.health_score,
  h.risk_description,
  h.scored_at,
  m.region_id                                         AS nem_region,
  m.rrp                                               AS spot_price_aud_mwh,
  m.price_timestamp,

  CASE
    WHEN m.rrp > 300 AND h.health_score < 0.5 THEN 'HIGH'
    WHEN m.rrp > 300 OR  h.health_score < 0.5 THEN 'MEDIUM'
    ELSE 'LOW'
  END                                                 AS market_risk_level

FROM health_scores h
INNER JOIN nem_market_snapshot m
  ON m.region_id = 'VIC1'
WHERE h.health_score IS NOT NULL;
