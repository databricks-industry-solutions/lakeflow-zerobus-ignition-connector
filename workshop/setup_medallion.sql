-- =============================================================================
-- Medallion Architecture Workshop: External Table Setup
-- =============================================================================
-- Prerequisites:
--   1. Storage credential exists in Unity Catalog (for your ADLS account)
--   2. External location exists covering:
--      abfss://__CONTAINER__@__STORAGE_ACCOUNT__.dfs.core.windows.net/
--   3. User has CREATE CATALOG, CREATE SCHEMA, CREATE TABLE privileges
--
-- Placeholders (replaced at runtime by run_setup_sql.py or sed):
--   __CATALOG__          = medallion (default)
--   __SOURCE_CATALOG__   = ot_demo  (existing demo data)
--   __SOURCE_SCHEMA__    = ot       (existing demo schema)
--   __STORAGE_ACCOUNT__  = your ADLS storage account name
--   __CONTAINER__        = medallion (ADLS container name)
--
-- Run with:
--   make workshop-setup           (all steps at once — pre-session)
--
-- Build-live approach (recommended for 2-hour workshop):
--   Pre-session:  Run Steps 1-3 only (catalog + schemas + bronze with data)
--   Bronze slide: Query bronze.raw_tags — data is already there
--   Silver slide: Run Steps 4-6 live in SQL editor (one at a time, show results)
--   Gold slide:   Run Steps 7-8 live (health_scores + revenue_risk)
--   Genie slide:  Run Step 9 (COMMENT ON) then open Genie room
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Step 1: Create the ADLS container (done outside SQL — via Azure CLI/portal)
-- ---------------------------------------------------------------------------
-- az storage container create --name __CONTAINER__ \
--   --account-name __STORAGE_ACCOUNT__ --auth-mode login

-- ---------------------------------------------------------------------------
-- Step 2: Create catalog and three schemas (the medallion layers)
-- ---------------------------------------------------------------------------
CREATE CATALOG IF NOT EXISTS __CATALOG__
  COMMENT 'Workshop: Medallion Architecture demo with external tables';

CREATE SCHEMA IF NOT EXISTS __CATALOG__.bronze
  COMMENT 'Raw data as-is from source. Append-only, no transforms.';

CREATE SCHEMA IF NOT EXISTS __CATALOG__.silver
  COMMENT 'Cleaned, validated, enriched data. Trusted for analytics.';

CREATE SCHEMA IF NOT EXISTS __CATALOG__.gold
  COMMENT 'Business-ready aggregates. One row per entity, dashboard-ready.';

-- ---------------------------------------------------------------------------
-- Step 3: Bronze layer — raw_tags (external table)
-- ---------------------------------------------------------------------------
-- Copies recent data from the existing demo into an external table with a
-- clean ADLS path the audience can browse in Azure portal.

CREATE OR REPLACE TABLE __CATALOG__.bronze.raw_tags (
  event_id              STRING      NOT NULL  COMMENT 'UUID per event',
  event_time            BIGINT      NOT NULL  COMMENT 'Source timestamp (microseconds since epoch)',
  tag_path              STRING      NOT NULL  COMMENT 'Full Ignition tag path — unparsed',
  tag_provider          STRING      NOT NULL  COMMENT 'Source provider e.g. agl_bess',
  numeric_value         DOUBLE                COMMENT 'Value for numeric tags',
  string_value          STRING                COMMENT 'Value for string tags',
  boolean_value         BOOLEAN               COMMENT 'Value for boolean tags',
  quality               STRING                COMMENT 'Quality indicator: GOOD, BAD, UNCERTAIN',
  quality_code          INT                   COMMENT 'OPC quality code (192 = Good)',
  source_system         STRING      NOT NULL  COMMENT 'Which gateway sent this event',
  ingestion_timestamp   BIGINT                COMMENT 'When we received it (microseconds since epoch)',
  data_type             STRING                COMMENT 'Original type: DOUBLE, STRING, BOOLEAN',
  sdt_compressed        BOOLEAN               COMMENT 'Survived SDT compression filter',
  compression_ratio     DOUBLE                COMMENT 'Running compression ratio at emission'
)
LOCATION 'abfss://__CONTAINER__@__STORAGE_ACCOUNT__.dfs.core.windows.net/bronze/raw_tags'
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true'
)
COMMENT 'Bronze: raw OT sensor events — every reading, exactly as received';

-- Populate with recent data from existing demo (last 2 hours for manageable size)
INSERT INTO __CATALOG__.bronze.raw_tags
SELECT
  event_id, event_time, tag_path, tag_provider,
  numeric_value, string_value, boolean_value,
  quality, quality_code, source_system, ingestion_timestamp,
  data_type, sdt_compressed, compression_ratio
FROM __SOURCE_CATALOG__.__SOURCE_SCHEMA__.raw_tags
WHERE ingestion_timestamp > unix_micros(current_timestamp() - INTERVAL 2 HOURS);


-- ---------------------------------------------------------------------------
-- Step 4: Silver layer — parsed_tags (external table)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE __CATALOG__.silver.parsed_tags (
  event_timestamp       TIMESTAMP   NOT NULL  COMMENT 'Human-readable event time',
  ingest_timestamp      TIMESTAMP             COMMENT 'When the platform received this event',
  asset_id              STRING      NOT NULL  COMMENT 'Extracted asset identifier e.g. tomago_bess_01',
  asset_type            STRING                COMMENT 'Asset classification e.g. battery_bess',
  tag_name              STRING      NOT NULL  COMMENT 'Signal path e.g. thermal/rack_temp_c',
  tag_value             DOUBLE                COMMENT 'Numeric value (coalesced)',
  tag_value_str         STRING                COMMENT 'String value for non-numeric tags',
  quality               STRING                COMMENT 'Quality indicator',
  source_system         STRING                COMMENT 'Source gateway'
)
LOCATION 'abfss://__CONTAINER__@__STORAGE_ACCOUNT__.dfs.core.windows.net/silver/parsed_tags'
COMMENT 'Silver: parsed tags with extracted asset_id and signal name';

-- Populate from existing parsed_tags (if available) or transform from bronze
INSERT INTO __CATALOG__.silver.parsed_tags
SELECT
  to_timestamp(event_time / 1000000)                                         AS event_timestamp,
  to_timestamp(ingestion_timestamp / 1000000)                                AS ingest_timestamp,
  lower(
    concat(
      regexp_extract(tag_path, '/([^/]+)/Site\\d+/', 1),
      '_',
      regexp_extract(tag_path, '/Site\\d+/([^/]+)/', 1)
    )
  )                                                                          AS asset_id,
  CASE
    WHEN tag_provider = 'agl_bess'   THEN 'battery_bess'
    WHEN tag_provider = 'agl_grid'   THEN 'grid_infrastructure'
    WHEN tag_provider = 'agl_market' THEN 'market_data'
    WHEN tag_provider = 'agl_cmms'   THEN 'maintenance'
    ELSE tag_provider
  END                                                                        AS asset_type,
  concat(
    regexp_extract(tag_path, '/Site\\d+/[^/]+/(.+)$', 1)
  )                                                                          AS tag_name,
  numeric_value                                                              AS tag_value,
  string_value                                                               AS tag_value_str,
  quality,
  source_system
FROM __CATALOG__.bronze.raw_tags
WHERE event_time IS NOT NULL
  AND length(tag_path) > 0;


-- ---------------------------------------------------------------------------
-- Step 5: Silver layer — aggregated_tags (external table)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE __CATALOG__.silver.aggregated_tags (
  window_start          TIMESTAMP   NOT NULL  COMMENT 'Start of 1-minute window',
  window_end            TIMESTAMP   NOT NULL  COMMENT 'End of 1-minute window',
  asset_id              STRING      NOT NULL  COMMENT 'Asset identifier',
  tag_name              STRING      NOT NULL  COMMENT 'Signal path',
  avg_value             DOUBLE                COMMENT 'Average value in window',
  min_value             DOUBLE                COMMENT 'Minimum value in window',
  max_value             DOUBLE                COMMENT 'Maximum value in window',
  stddev_value          DOUBLE                COMMENT 'Standard deviation in window',
  sample_count          BIGINT                COMMENT 'Number of readings in window'
)
LOCATION 'abfss://__CONTAINER__@__STORAGE_ACCOUNT__.dfs.core.windows.net/silver/aggregated_tags'
COMMENT 'Silver: 1-minute windowed aggregations per asset per signal';

INSERT INTO __CATALOG__.silver.aggregated_tags
SELECT
  date_trunc('minute', event_timestamp)                  AS window_start,
  date_trunc('minute', event_timestamp) + INTERVAL 1 MINUTE AS window_end,
  asset_id,
  tag_name,
  AVG(tag_value)                                         AS avg_value,
  MIN(tag_value)                                         AS min_value,
  MAX(tag_value)                                         AS max_value,
  STDDEV(tag_value)                                      AS stddev_value,
  COUNT(*)                                               AS sample_count
FROM __CATALOG__.silver.parsed_tags
WHERE tag_value IS NOT NULL
GROUP BY date_trunc('minute', event_timestamp), asset_id, tag_name;


-- ---------------------------------------------------------------------------
-- Step 6: Silver layer — enriched_tags (external table)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE __CATALOG__.silver.enriched_tags (
  window_start          TIMESTAMP   NOT NULL  COMMENT '1-minute window start',
  window_end            TIMESTAMP   NOT NULL  COMMENT '1-minute window end',
  asset_id              STRING      NOT NULL  COMMENT 'Asset identifier',
  tag_name              STRING      NOT NULL  COMMENT 'Raw signal path',
  signal_name           STRING                COMMENT 'Human-readable signal name',
  unit                  STRING                COMMENT 'Engineering unit (°C, MW, %, Hz)',
  source_domain         STRING                COMMENT 'Data domain (battery_thermal, grid_power, ...)',
  avg_value             DOUBLE                COMMENT 'Average in window',
  min_value             DOUBLE                COMMENT 'Minimum in window',
  max_value             DOUBLE                COMMENT 'Maximum in window',
  stddev_value          DOUBLE                COMMENT 'Standard deviation in window',
  sample_count          BIGINT                COMMENT 'Readings in window'
)
LOCATION 'abfss://__CONTAINER__@__STORAGE_ACCOUNT__.dfs.core.windows.net/silver/enriched_tags'
COMMENT 'Silver: aggregated tags enriched with signal names, units, and domains';

INSERT INTO __CATALOG__.silver.enriched_tags
SELECT
  a.window_start, a.window_end, a.asset_id, a.tag_name,
  -- Derive human-readable signal name from tag_name path
  CASE
    WHEN a.tag_name LIKE '%/soc_pct'          THEN 'State of Charge'
    WHEN a.tag_name LIKE '%/soh_pct'          THEN 'State of Health'
    WHEN a.tag_name LIKE '%/rack_temp_c'      THEN 'Rack Temperature'
    WHEN a.tag_name LIKE '%/ambient_temp_c'   THEN 'Ambient Temperature'
    WHEN a.tag_name LIKE '%/active_power_mw'  THEN 'Active Power'
    WHEN a.tag_name LIKE '%/net_mw'           THEN 'Net Power (POI)'
    WHEN a.tag_name LIKE '%/frequency_hz'     THEN 'Grid Frequency'
    WHEN a.tag_name LIKE '%/voltage_kv'       THEN 'Voltage'
    WHEN a.tag_name LIKE '%/rrp_aud_mwh'     THEN 'Spot Price (RRP)'
    ELSE replace(regexp_extract(a.tag_name, '[^/]+$', 0), '_', ' ')
  END                                         AS signal_name,
  CASE
    WHEN a.tag_name LIKE '%_pct'     THEN '%'
    WHEN a.tag_name LIKE '%_temp_c'  THEN '°C'
    WHEN a.tag_name LIKE '%_mw'      THEN 'MW'
    WHEN a.tag_name LIKE '%_hz'      THEN 'Hz'
    WHEN a.tag_name LIKE '%_kv'      THEN 'kV'
    WHEN a.tag_name LIKE '%_aud%'    THEN 'AUD/MWh'
    ELSE NULL
  END                                         AS unit,
  CASE
    WHEN a.tag_name LIKE 'thermal/%'  THEN 'battery_thermal'
    WHEN a.tag_name LIKE 'power/%'    THEN 'battery_power'
    WHEN a.tag_name LIKE 'poi/%'      THEN 'grid_power'
    WHEN a.tag_name LIKE 'dispatch/%' THEN 'grid_dispatch'
    WHEN a.tag_name LIKE 'market/%'   THEN 'market_data'
    ELSE 'other'
  END                                         AS source_domain,
  a.avg_value, a.min_value, a.max_value, a.stddev_value, a.sample_count
FROM __CATALOG__.silver.aggregated_tags a;


-- ---------------------------------------------------------------------------
-- Step 7: Gold layer — health_scores (external table)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE __CATALOG__.gold.health_scores (
  scored_at               TIMESTAMP   NOT NULL  COMMENT 'When this score was computed',
  asset_id                STRING      NOT NULL  COMMENT 'Asset identifier',
  health_score            DOUBLE      NOT NULL  COMMENT 'Overall health 0.0 (critical) to 1.0 (healthy)',
  primary_risk_tag        STRING                COMMENT 'Signal contributing most to risk',
  risk_description        STRING                COMMENT 'Human-readable risk summary',
  anomaly_count           INT                   COMMENT 'Number of anomalous signals',
  total_key_tags          INT                   COMMENT 'Total key signals monitored',
  estimated_hours_to_failure DOUBLE             COMMENT 'Estimated hours to potential failure'
)
LOCATION 'abfss://__CONTAINER__@__STORAGE_ACCOUNT__.dfs.core.windows.net/gold/health_scores'
COMMENT 'Gold: per-asset health score — one row per asset, updated continuously';

-- Compute health scores using z-score anomaly detection on key signals
INSERT INTO __CATALOG__.gold.health_scores
WITH asset_signal_stats AS (
  -- Rolling statistics per asset per signal (last 1 hour)
  SELECT
    asset_id,
    tag_name,
    AVG(avg_value)    AS mean_val,
    STDDEV(avg_value) AS stddev_val,
    COUNT(*)          AS window_count
  FROM __CATALOG__.silver.enriched_tags
  WHERE window_start > current_timestamp() - INTERVAL 1 HOUR
    AND avg_value IS NOT NULL
  GROUP BY asset_id, tag_name
),
latest_values AS (
  -- Most recent value per asset per signal
  SELECT asset_id, tag_name, avg_value,
    ROW_NUMBER() OVER (PARTITION BY asset_id, tag_name ORDER BY window_start DESC) AS rn
  FROM __CATALOG__.silver.enriched_tags
  WHERE window_start > current_timestamp() - INTERVAL 1 HOUR
),
anomalies AS (
  -- Z-score anomaly detection: flag signals > 2 std devs from mean
  SELECT
    s.asset_id,
    s.tag_name,
    CASE
      WHEN s.stddev_val > 0 AND ABS(l.avg_value - s.mean_val) / s.stddev_val > 2.0
      THEN true ELSE false
    END AS is_anomalous,
    CASE
      WHEN s.stddev_val > 0
      THEN ABS(l.avg_value - s.mean_val) / s.stddev_val
      ELSE 0.0
    END AS zscore
  FROM asset_signal_stats s
  JOIN latest_values l ON s.asset_id = l.asset_id AND s.tag_name = l.tag_name AND l.rn = 1
  WHERE s.window_count >= 5  -- need enough data points
    AND s.tag_name RLIKE '(soc_pct|soh_pct|rack_temp_c|active_power_mw|frequency_hz|voltage_kv|net_mw)'
),
scored AS (
  SELECT
    asset_id,
    COUNT(*)                                          AS total_key_tags,
    SUM(CASE WHEN is_anomalous THEN 1 ELSE 0 END)   AS anomaly_count,
    MAX(CASE WHEN is_anomalous THEN tag_name END)    AS primary_risk_tag,
    MAX(CASE WHEN is_anomalous THEN zscore END)      AS max_zscore
  FROM anomalies
  GROUP BY asset_id
)
SELECT
  current_timestamp()                                         AS scored_at,
  asset_id,
  ROUND(1.0 - (anomaly_count / CAST(total_key_tags AS DOUBLE)), 2) AS health_score,
  primary_risk_tag,
  CASE
    WHEN anomaly_count = 0 THEN 'All signals within normal range'
    WHEN anomaly_count = 1 THEN concat('1 signal anomalous: ', coalesce(primary_risk_tag, 'unknown'))
    ELSE concat(anomaly_count, ' signals anomalous — investigate ', coalesce(primary_risk_tag, 'unknown'))
  END                                                         AS risk_description,
  anomaly_count,
  total_key_tags,
  ROUND(720.0 * POWER(1.0 - (anomaly_count / CAST(total_key_tags AS DOUBLE)), 2), 0) AS estimated_hours_to_failure
FROM scored;


-- ---------------------------------------------------------------------------
-- Step 8: Gold layer — revenue_risk (external table)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE __CATALOG__.gold.revenue_risk (
  computed_at             TIMESTAMP   NOT NULL  COMMENT 'When this was computed',
  asset_id                STRING      NOT NULL  COMMENT 'Asset identifier',
  health_score            DOUBLE                COMMENT 'Current health score',
  trip_probability        DOUBLE                COMMENT 'Probability of asset tripping (1 - health_score)',
  capacity_mw             DOUBLE                COMMENT 'Asset capacity in MW',
  forecast_price_aud_mwh  DOUBLE                COMMENT 'Forecast energy price AUD/MWh',
  risk_window_hours       DOUBLE                COMMENT 'Duration of risk window in hours',
  revenue_at_risk_aud     DOUBLE                COMMENT 'Revenue at risk in AUD',
  recommended_action      STRING                COMMENT 'Recommended operator action'
)
LOCATION 'abfss://__CONTAINER__@__STORAGE_ACCOUNT__.dfs.core.windows.net/gold/revenue_risk'
COMMENT 'Gold: revenue at risk per asset during high-price windows';

INSERT INTO __CATALOG__.gold.revenue_risk
SELECT
  current_timestamp()                                        AS computed_at,
  h.asset_id,
  h.health_score,
  ROUND(1.0 - h.health_score, 2)                            AS trip_probability,
  -- Default capacities per asset type pattern
  CASE
    WHEN h.asset_id LIKE '%bess%'       THEN 500.0
    WHEN h.asset_id LIKE '%substation%' THEN 500.0
    ELSE 50.0
  END                                                        AS capacity_mw,
  350.0                                                      AS forecast_price_aud_mwh,
  4.0                                                        AS risk_window_hours,
  ROUND(
    CASE WHEN h.asset_id LIKE '%bess%' THEN 500.0 ELSE 50.0 END
    * 4.0 * 350.0 * (1.0 - h.health_score),
    2
  )                                                          AS revenue_at_risk_aud,
  CASE
    WHEN h.health_score >= 0.9 THEN 'No action required'
    WHEN h.health_score >= 0.7 THEN 'Monitor — schedule inspection'
    WHEN h.health_score >= 0.5 THEN 'Inspect before next high-price window'
    ELSE 'Immediate inspection required — consider curtailment'
  END                                                        AS recommended_action
FROM __CATALOG__.gold.health_scores h
WHERE h.health_score < 1.0;


-- ---------------------------------------------------------------------------
-- Step 9: Genie-ready metadata (COMMENT ON for AI/BI discoverability)
-- ---------------------------------------------------------------------------
-- These narrative descriptions make gold tables queryable via Genie (AI/BI).
-- Run this AFTER gold tables are populated — it's the "Genie enablement" step.

COMMENT ON TABLE __CATALOG__.gold.health_scores IS
  'Per-asset health score using z-score anomaly detection on key OT signals. One row per asset. Score ranges from 0.0 (critical — multiple signals anomalous) to 1.0 (healthy — all signals within normal range). Updated every pipeline run. Use this table to find which assets need inspection, sorted by health_score ascending.';

COMMENT ON TABLE __CATALOG__.gold.revenue_risk IS
  'Revenue at risk per asset during the next high-price dispatch window. Combines asset health from OT sensors with energy market price forecasts and asset capacity. One row per at-risk asset (health_score < 1.0). revenue_at_risk_aud = capacity_mw × risk_window_hours × forecast_price × (1 - health_score).';

COMMENT ON TABLE __CATALOG__.silver.enriched_tags IS
  'Silver layer: 1-minute aggregated sensor readings enriched with human-readable signal names, engineering units, and source domains. Replaces PI Asset Framework element templates. One row per asset per signal per minute.';

COMMENT ON TABLE __CATALOG__.bronze.raw_tags IS
  'Bronze layer: raw OT sensor events exactly as received from PI/Ignition via Zerobus. Every reading, every tag, append-only. Source timestamps are microsecond BIGINTs. Tag paths are packed strings from the Ignition tag tree. This is the system of record.';


-- ---------------------------------------------------------------------------
-- Summary: What we just created
-- ---------------------------------------------------------------------------
-- SELECT 'bronze.raw_tags'       AS table_name, COUNT(*) AS rows FROM __CATALOG__.bronze.raw_tags
-- UNION ALL
-- SELECT 'silver.parsed_tags',   COUNT(*) FROM __CATALOG__.silver.parsed_tags
-- UNION ALL
-- SELECT 'silver.aggregated_tags', COUNT(*) FROM __CATALOG__.silver.aggregated_tags
-- UNION ALL
-- SELECT 'silver.enriched_tags', COUNT(*) FROM __CATALOG__.silver.enriched_tags
-- UNION ALL
-- SELECT 'gold.health_scores',   COUNT(*) FROM __CATALOG__.gold.health_scores
-- UNION ALL
-- SELECT 'gold.revenue_risk',    COUNT(*) FROM __CATALOG__.gold.revenue_risk;
