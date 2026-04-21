-- AGL OT Lakehouse Demo - Table Setup
-- Usage: Run against your Databricks SQL Warehouse.
-- Replace ${catalog} and ${schema} with your target catalog/schema,
-- or set them as query parameters (e.g., agl_demo.ot).

-- 1. Bronze: raw tag events from Ignition via Zerobus
CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.raw_tags (
  event_timestamp   TIMESTAMP   NOT NULL COMMENT 'Source timestamp from Ignition',
  ingest_timestamp  TIMESTAMP   NOT NULL COMMENT 'Time Zerobus persists to Delta',
  asset_id          STRING      NOT NULL COMMENT 'Unique asset identifier (e.g. wind_hexham_t01)',
  asset_type        STRING      NOT NULL COMMENT 'wind_turbine | battery_bess | solar | gas',
  tag_name          STRING      NOT NULL COMMENT 'Full tag path (e.g. generator/speed_rpm)',
  tag_value         DOUBLE      NOT NULL COMMENT 'Numeric value',
  quality           INT         NOT NULL COMMENT 'OPC quality code (192 = good)',
  source_system     STRING      NOT NULL COMMENT 'ignition_sim for demo',
  sdt_compressed    BOOLEAN     NOT NULL COMMENT 'True if this record survived SDT compression',
  compression_ratio DOUBLE               COMMENT 'Running ratio of raw-to-compressed events per tag'
)
COMMENT 'Bronze layer: raw OT tag change events from Ignition via Zerobus';

-- 2. Silver: windowed aggregations
CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.aggregated_tags (
  window_start      TIMESTAMP   NOT NULL COMMENT 'Aggregation window start',
  window_end        TIMESTAMP   NOT NULL COMMENT 'Aggregation window end',
  asset_id          STRING      NOT NULL COMMENT 'Asset identifier',
  tag_name          STRING      NOT NULL COMMENT 'Tag path',
  avg_value         DOUBLE               COMMENT 'Mean value in window',
  min_value         DOUBLE               COMMENT 'Min value in window',
  max_value         DOUBLE               COMMENT 'Max value in window',
  stddev_value      DOUBLE               COMMENT 'Std deviation in window',
  sample_count      INT                  COMMENT 'Raw samples in window',
  compressed_count  INT                  COMMENT 'Post-SDT samples in window'
)
COMMENT 'Silver layer: windowed tag aggregations';

-- 3. Ingest metrics (5-second windows)
CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.ingest_metrics (
  window_start          TIMESTAMP   NOT NULL COMMENT '5-second window start',
  window_end            TIMESTAMP   NOT NULL COMMENT '5-second window end',
  records_raw           LONG                 COMMENT 'Records generated before SDT',
  records_after_sdt     LONG                 COMMENT 'Records that survived SDT compression',
  bytes_estimate        LONG                 COMMENT 'Approximate bytes written to Delta',
  avg_latency_ms        DOUBLE               COMMENT 'Avg ingest_timestamp - event_timestamp in ms',
  p99_latency_ms        DOUBLE               COMMENT 'P99 latency in ms',
  tags_active           LONG                 COMMENT 'Distinct tags seen in window',
  sdt_compression_ratio DOUBLE               COMMENT 'records_raw / records_after_sdt'
)
COMMENT 'Ingest throughput and latency metrics per 5-second window';

-- 4. SDT configuration per tag pattern
CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.sdt_config (
  tag_pattern       STRING      NOT NULL COMMENT 'Glob pattern matching tag names (e.g. */temperature_c)',
  comp_dev          DOUBLE               COMMENT 'Compression deviation (engineering units)',
  comp_dev_percent  DOUBLE               COMMENT 'CompDev as % of tag span',
  comp_max_seconds  INT                  COMMENT 'Max time before forcing an archive event',
  comp_min_seconds  INT                  COMMENT 'Min time between archived events'
)
COMMENT 'Swinging Door Trending compression configuration per tag pattern';

-- Pre-populate SDT defaults per signal class.
-- comp_dev = absolute deviation band (engineering units).
-- comp_dev_percent = deviation as % of span (used when absolute not set).
-- comp_max_seconds = heartbeat interval (forces archive even if value steady).
-- comp_min_seconds = minimum time between archives (rate-limit noisy tags).
MERGE INTO ${catalog}.${schema}.sdt_config AS target
USING (
  SELECT * FROM VALUES
    -- Catch-all: conservative 2% deviation, 2-minute heartbeat
    ('*',                           NULL, 2.0,  120,  0),

    -- === BESS / Battery ===
    ('*/soc_pct',                   0.25, NULL, 300,  1),  -- SoC: 0.25% abs, 5-min heartbeat (slow-changing)
    ('*/soh_pct',                   0.05, NULL, 900,  5),  -- SoH: 0.05% abs, 15-min heartbeat (glacial)
    ('*/energy_available_mwh',      0.5,  NULL, 300,  1),  -- Energy: 0.5 MWh, 5-min
    ('*/bess_active_power_mw',      NULL, 1.0,  30,   0),  -- BESS power: 1% of span, 30s heartbeat (fast-changing)
    ('*/bess_reactive_power_mvar',  NULL, 2.0,  60,   0),  -- Reactive: 2% of span, 1-min
    ('*/dccurrent_a',               NULL, 1.5,  30,   0),  -- DC current: 1.5% span, 30s (tracks power)
    ('*/dcvoltage_v',               2.0,  NULL, 120,  1),  -- DC voltage: 2V abs, 2-min

    -- === Thermal ===
    ('*/temperature_c',             0.3,  NULL, 300,  1),  -- Ambient/coolant temp: 0.3C, 5-min
    ('*/ambient_temp_c',            0.3,  NULL, 600,  2),  -- Ambient: 0.3C, 10-min (very slow)
    ('*/max_rack_temp_c',           0.5,  NULL, 120,  1),  -- Rack temp: 0.5C, 2-min (safety-critical)
    ('*/coolant*temp_c',            0.3,  NULL, 300,  1),  -- Coolant: 0.3C, 5-min

    -- === Grid / POI ===
    ('*/poi_frequency_hz',          0.005, NULL, 30,  0),  -- Grid freq: 5mHz abs, 30s (very tight, safety)
    ('*/frequency_hz',              0.005, NULL, 30,  0),  -- Frequency: 5mHz abs, 30s
    ('*/poi_voltage_kv',            0.1,  NULL, 60,   0),  -- Grid voltage: 0.1kV abs, 1-min
    ('*/voltage_kv',                0.1,  NULL, 60,   0),  -- Voltage: 0.1kV abs, 1-min
    ('*/poi_export_mw',             NULL, 1.0,  30,   0),  -- Export power: 1% span, 30s
    ('*/poi_import_mw',             NULL, 1.0,  30,   0),  -- Import power: 1% span, 30s
    ('*/poi_net_mw',                NULL, 1.0,  30,   0),  -- Net power: 1% span, 30s (dispatch-critical)
    ('*/dispatch_target_mw',        NULL, 0.5,  15,   0),  -- Dispatch target: 0.5% span, 15s (control signal)
    ('*/curtailment_pct',           1.0,  NULL, 60,   0),  -- Curtailment: 1% abs, 1-min

    -- === Market ===
    ('*/rrp_aud_per_mwh',           5.0,  NULL, 60,   0),  -- Spot price: $5 abs, 1-min (volatile)
    ('*/fcas_*_price',              NULL, 2.0,  60,   0),  -- FCAS prices: 2% span, 1-min

    -- === Power (general) ===
    ('*/power_kw',                  NULL, 1.0,  60,   0),  -- Power kW: 1% span, 1-min
    ('*/power_mw',                  NULL, 1.0,  30,   0),  -- Power MW: 1% span, 30s
    ('*/activepower_mw',            NULL, 1.0,  30,   0),  -- Active power: 1% span, 30s
    ('*/reactivepower_mvar',        NULL, 2.0,  60,   0),  -- Reactive: 2% span, 1-min

    -- === CMMS / Counters ===
    ('*/alarm*',                    1.0,  NULL, 300,  2),  -- Alarm counts: 1 abs, 5-min
    ('*/work_orders',               1.0,  NULL, 600,  5),  -- Work orders: 1 abs, 10-min (slow)
    ('*/*_count',                   1.0,  NULL, 300,  2),  -- Generic counts: 1 abs, 5-min

    -- === Max charge/discharge limits ===
    ('*/max_charge_mw',             NULL, 1.0,  120,  1),  -- Charge limit: 1% span, 2-min
    ('*/max_discharge_mw',          NULL, 1.0,  120,  1)   -- Discharge limit: 1% span, 2-min
  AS defaults(tag_pattern, comp_dev, comp_dev_percent, comp_max_seconds, comp_min_seconds)
) AS source
ON target.tag_pattern = source.tag_pattern
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

-- 5. Asset metadata
CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.assets (
  asset_id          STRING      NOT NULL COMMENT 'Primary key',
  asset_name        STRING      NOT NULL COMMENT 'Display name',
  asset_type        STRING      NOT NULL COMMENT 'wind_turbine / battery_bess',
  site_name         STRING      NOT NULL COMMENT 'e.g. Hexham, Liddell, Tomago',
  capacity_mw       DOUBLE               COMMENT 'Rated capacity in MW',
  latitude          DOUBLE               COMMENT 'For map display',
  longitude         DOUBLE               COMMENT 'For map display',
  commissioned_date DATE                 COMMENT 'Nullable',
  tag_count         INT                  COMMENT 'Number of tags per asset'
)
COMMENT 'Asset metadata for wind turbines and battery BESS units';
