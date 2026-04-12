-- AGL Fleet Simulator - Databricks catalog/schema setup
-- Run this in a Databricks SQL Warehouse or notebook before starting the simulator.
--
-- IMPORTANT: Run as a user that has CREATE CATALOG on the metastore (e.g. workspace admin).
-- The app/service principal (agl-demo profile) does not have CREATE CATALOG; run this once
-- in the SQL Editor or with a user profile, then the SP can use the catalog.
--
-- Creates:
--   __CATALOG__              catalog (uses metastore default root; no MANAGED LOCATION in this script)
--   __CATALOG__.__SCHEMA__   schema
--   __CATALOG__.__SCHEMA__.raw_tags  (Bronze - Zerobus writes here)
--   Asset Framework + SDP silver tables in same schema (ot).
--
-- Placeholders __CATALOG__ and __SCHEMA__ are replaced by run_setup_sql.py from env
-- (CATALOG, SCHEMA; defaults agl_demo, ot). After running this, run setup_asset_framework.sql.

-- 0. Catalog and schema (uses metastore default location if MANAGED LOCATION omitted)
--    Optional: set env MANAGED_LOCATION to a path (e.g. abfss://container@storage.dfs.core.windows.net/path)
--    and use __MANAGED_LOCATION__ in the CREATE CATALOG line for a custom root.
CREATE CATALOG IF NOT EXISTS __CATALOG__;
CREATE SCHEMA IF NOT EXISTS __CATALOG__.__SCHEMA__
  COMMENT 'OT data from Ignition via Zerobus connector';

-- 1. Bronze: Zerobus landing table - schema matches OTEvent protobuf exactly.
--    Zerobus may auto-create this table, but pre-creating ensures column comments and correct types.
--    Compression: DBR 16+ uses ZSTD by default for new managed tables; we do not set it explicitly.
--    Primary key improves dedup/merge queries.
--    Drop leftover view or table so we can (re)create the table (raw_tags was a compat view; now it's the table).
DROP VIEW IF EXISTS __CATALOG__.__SCHEMA__.raw_tags;
DROP TABLE IF EXISTS __CATALOG__.__SCHEMA__.raw_tags;
CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.raw_tags (
  event_id              STRING      NOT NULL  COMMENT 'UUID per event',
  event_time            BIGINT      NOT NULL  COMMENT 'Source timestamp (micros since epoch)',
  tag_path              STRING      NOT NULL  COMMENT 'Full Ignition tag path e.g. [agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/SoC_pct',
  tag_provider          STRING      NOT NULL  COMMENT 'Ignition tag provider extracted from path e.g. agl_bess',
  numeric_value         DOUBLE                COMMENT 'Value for numeric tags',
  string_value          STRING                COMMENT 'Value for string tags',
  boolean_value         BOOLEAN               COMMENT 'Value for boolean tags',
  quality               STRING                COMMENT 'Quality string e.g. Good',
  quality_code          INT                   COMMENT 'OPC quality code (192 = Good)',
  source_system         STRING                COMMENT 'Source gateway identifier',
  ingestion_timestamp   BIGINT                COMMENT 'Ingestion timestamp (micros since epoch)',
  data_type             STRING                COMMENT 'Original data type: DOUBLE, STRING, BOOLEAN',
  alarm_state           STRING                COMMENT 'Alarm state if applicable',
  alarm_priority        INT                   COMMENT 'Alarm priority if applicable',
  sdt_compressed        BOOLEAN               COMMENT 'True if survived SDT compression',
  compression_ratio    DOUBLE                COMMENT 'Running ratio at emission; 0 when SDT off',
  sdt_enabled           BOOLEAN               COMMENT 'Gateway config: SDT was on when this event was sent',
  batch_bytes_sent      BIGINT                COMMENT 'Size in bytes of the batch this event was sent in (demo observability)',
  CONSTRAINT raw_tags_pk PRIMARY KEY (event_id)
)
-- NOTE: Do NOT use CLUSTER BY here. Zerobus Ingest rejects stream creation (INTERNAL/1521)
-- on tables with liquid clustering enabled. Add clustering on downstream silver/gold tables instead.
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
COMMENT 'Bronze layer: raw OT tag events from Ignition via Zerobus (matches OTEvent protobuf)';

-- 1b. Enable CDF on raw_tags if table already existed (idempotent).
ALTER TABLE __CATALOG__.__SCHEMA__.raw_tags SET TBLPROPERTIES (delta.enableChangeDataFeed = 'true');

-- 1c. For existing raw_tags created without PK (run once).
-- ALTER TABLE __CATALOG__.__SCHEMA__.raw_tags ADD CONSTRAINT raw_tags_pk PRIMARY KEY (event_id);
--
-- WARNING: Do NOT enable liquid clustering while Zerobus is writing to this table.
-- Zerobus Ingest rejects stream creation (INTERNAL/1521) on CLUSTER BY tables.
-- See onboarding/ZEROBUS_CLUSTER_BY_BUG.md for full compatibility matrix.

-- 2. Asset Framework tables
--    See pipelines/sql/setup_asset_framework.sql for full DDL + seed data.
--    Repeated here so this single script bootstraps everything.

CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.asset_templates (
  template_id STRING NOT NULL,
  template_name STRING NOT NULL,
  description STRING,
  base_asset_type STRING NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT asset_templates_pk PRIMARY KEY (template_id)
)
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');

CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.template_attributes (
  attribute_id STRING NOT NULL,
  template_id STRING NOT NULL,
  attribute_name STRING NOT NULL,
  data_type STRING NOT NULL,
  unit STRING,
  default_value STRING,
  is_required BOOLEAN DEFAULT false,
  sort_order INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT template_attributes_pk PRIMARY KEY (attribute_id),
  CONSTRAINT template_attributes_fk FOREIGN KEY (template_id) REFERENCES __CATALOG__.__SCHEMA__.asset_templates(template_id)
)
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');

CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.asset_hierarchy (
  asset_id STRING NOT NULL,
  parent_asset_id STRING,
  asset_name STRING NOT NULL,
  asset_type STRING NOT NULL,
  template_id STRING,
  site_name STRING,
  description STRING,
  capacity_mw DOUBLE            COMMENT 'Rated capacity in MW (equipment only)',
  latitude DOUBLE               COMMENT 'GPS latitude for map display',
  longitude DOUBLE              COMMENT 'GPS longitude for map display',
  tag_count INT                 COMMENT 'Number of streaming tags for this asset',
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT asset_hierarchy_pk PRIMARY KEY (asset_id),
  CONSTRAINT asset_hierarchy_template_fk FOREIGN KEY (template_id) REFERENCES __CATALOG__.__SCHEMA__.asset_templates(template_id)
)
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');

CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.asset_attribute_values (
  asset_id STRING NOT NULL,
  attribute_id STRING NOT NULL,
  value STRING,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT asset_attribute_values_pk PRIMARY KEY (asset_id, attribute_id),
  CONSTRAINT asset_attr_values_asset_fk FOREIGN KEY (asset_id) REFERENCES __CATALOG__.__SCHEMA__.asset_hierarchy(asset_id),
  CONSTRAINT asset_attr_values_attr_fk FOREIGN KEY (attribute_id) REFERENCES __CATALOG__.__SCHEMA__.template_attributes(attribute_id)
)
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');

-- 2b. SDT configuration per tag pattern (used by app Compression page tuning panel)
CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.sdt_config (
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
MERGE INTO __CATALOG__.__SCHEMA__.sdt_config AS target
USING (
  SELECT * FROM VALUES
    -- Catch-all: conservative 2% deviation, 2-minute heartbeat
    ('*',                           NULL, 2.0,  120,  0),

    -- === BESS / Battery ===
    ('*/soc_pct',                   0.25, NULL, 300,  1),
    ('*/soh_pct',                   0.05, NULL, 900,  5),
    ('*/energy_available_mwh',      0.5,  NULL, 300,  1),
    ('*/bess_active_power_mw',      NULL, 1.0,  30,   0),
    ('*/bess_reactive_power_mvar',  NULL, 2.0,  60,   0),
    ('*/dccurrent_a',               NULL, 1.5,  30,   0),
    ('*/dcvoltage_v',               2.0,  NULL, 120,  1),

    -- === Thermal ===
    ('*/temperature_c',             0.3,  NULL, 300,  1),
    ('*/ambient_temp_c',            0.3,  NULL, 600,  2),
    ('*/max_rack_temp_c',           0.5,  NULL, 120,  1),
    ('*/coolant*temp_c',            0.3,  NULL, 300,  1),

    -- === Grid / POI ===
    ('*/poi_frequency_hz',          0.005, NULL, 30,  0),
    ('*/frequency_hz',              0.005, NULL, 30,  0),
    ('*/poi_voltage_kv',            0.1,  NULL, 60,   0),
    ('*/voltage_kv',                0.1,  NULL, 60,   0),
    ('*/poi_export_mw',             NULL, 1.0,  30,   0),
    ('*/poi_import_mw',             NULL, 1.0,  30,   0),
    ('*/poi_net_mw',                NULL, 1.0,  30,   0),
    ('*/dispatch_target_mw',        NULL, 0.5,  15,   0),
    ('*/curtailment_pct',           1.0,  NULL, 60,   0),

    -- === Market ===
    ('*/rrp_aud_per_mwh',           5.0,  NULL, 60,   0),
    ('*/fcas_*_price',              NULL, 2.0,  60,   0),

    -- === Power (general) ===
    ('*/power_kw',                  NULL, 1.0,  60,   0),
    ('*/power_mw',                  NULL, 1.0,  30,   0),
    ('*/activepower_mw',            NULL, 1.0,  30,   0),
    ('*/reactivepower_mvar',        NULL, 2.0,  60,   0),

    -- === CMMS / Counters ===
    ('*/alarm*',                    1.0,  NULL, 300,  2),
    ('*/work_orders',               1.0,  NULL, 600,  5),
    ('*/*_count',                   1.0,  NULL, 300,  2),

    -- === Max charge/discharge limits ===
    ('*/max_charge_mw',             NULL, 1.0,  120,  1),
    ('*/max_discharge_mw',          NULL, 1.0,  120,  1)
  AS defaults(tag_pattern, comp_dev, comp_dev_percent, comp_max_seconds, comp_min_seconds)
) AS source
ON target.tag_pattern = source.tag_pattern
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

-- 3. Volume for Python wheels (e.g. agl_analytics) – reference in jobs/apps as:
--    /Volumes/__CATALOG__/__SCHEMA__/wheels/agl_analytics-0.1.0-py3-none-any.whl
CREATE VOLUME IF NOT EXISTS __CATALOG__.__SCHEMA__.wheels
  COMMENT 'Python wheels for jobs and apps (e.g. agl_analytics)';

-- 3b. SDP pipeline silver tables in __SCHEMA__ (ot)
-- silver_asset_registry is now a VIEW created in setup_asset_framework.sql
-- Drop whichever old object type exists so the VIEW can be created
DROP VIEW IF EXISTS __CATALOG__.__SCHEMA__.silver_asset_registry;
DROP TABLE IF EXISTS __CATALOG__.__SCHEMA__.silver_asset_registry;
CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.silver_signal_mapping (
  tag_path STRING,
  asset_id STRING,
  signal_name STRING,
  unit STRING,
  scale DOUBLE,
  offset DOUBLE,
  source_domain STRING,
  active BOOLEAN
) USING DELTA;

-- 3c. silver_asset_registry seed data is now in setup_asset_framework.sql
-- (the VIEW reads from asset_hierarchy which has the canonical seed data)

-- 3d. Seed silver_signal_mapping (idempotent MERGE on tag_path)
MERGE INTO __CATALOG__.__SCHEMA__.silver_signal_mapping AS target
USING (
  SELECT * FROM VALUES
    -- BESS telemetry (agl_bess)
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/SoC_pct',             'bess01', 'soc_pct',                '%',     1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/SoH_pct',             'bess01', 'soh_pct',                '%',     1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/EnergyAvailable_MWh', 'bess01', 'energy_available_mwh',   'MWh',   1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/ActivePower_MW',      'bess01', 'bess_active_power_mw',   'MW',    1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/ReactivePower_MVAr',  'bess01', 'bess_reactive_power_mvar','MVAr', 1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/Mode',                'bess01', 'mode',                   'enum',  1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/DerateActive',        'bess01', 'derate_active',          'bool',  1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/DerateReason',        'bess01', 'derate_reason',          'string',1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Thermal/AmbientTemp_C',         'bess01', 'ambient_temp_c',         'C',     1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Thermal/HVAC_Running',          'bess01', 'hvac_running',           'bool',  1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Thermal/MaxRackTemp_C',         'bess01', 'max_rack_temp_c',        'C',     1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Limits/MaxCharge_MW',           'bess01', 'max_charge_mw',          'MW',    1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Limits/MaxDischarge_MW',        'bess01', 'max_discharge_mw',       'MW',    1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Alarms/AlarmCount',             'bess01', 'alarm_count',            'count', 1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Alarms/CriticalAlarmActive',    'bess01', 'critical_alarm_active',  'bool',  1.0, 0.0, 'bess', true),
    ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Alarms/LastAlarm',              'bess01', 'last_alarm',             'string',1.0, 0.0, 'bess', true),
    -- Grid / dispatch (agl_grid)
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Substation01/POI/ExportPower_MW',      'substation01', 'poi_export_mw',       'MW',    1.0, 0.0, 'grid', true),
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Substation01/POI/ImportPower_MW',      'substation01', 'poi_import_mw',       'MW',    1.0, 0.0, 'grid', true),
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Substation01/POI/NetPower_MW',         'substation01', 'poi_net_mw',          'MW',    1.0, 0.0, 'grid', true),
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Substation01/POI/Voltage_kV',          'substation01', 'poi_voltage_kv',      'kV',    1.0, 0.0, 'grid', true),
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Substation01/POI/Frequency_Hz',        'substation01', 'poi_frequency_hz',    'Hz',    1.0, 0.0, 'grid', true),
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Dispatch/TargetNetPower_MW',           'tomago_site01','dispatch_target_mw',   'MW',    1.0, 0.0, 'grid', true),
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Dispatch/ConstraintActive',            'tomago_site01','constraint_active',    'bool',  1.0, 0.0, 'grid', true),
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Dispatch/ConstraintReason',            'tomago_site01','constraint_reason',    'string',1.0, 0.0, 'grid', true),
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Dispatch/Curtailment_pct',             'tomago_site01','curtailment_pct',      '%',     1.0, 0.0, 'grid', true),
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Dispatch/FCAS_Enabled',                'tomago_site01','fcas_enabled',         'bool',  1.0, 0.0, 'grid', true),
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Events/FrequencyEventActive',          'tomago_site01','frequency_event_active','bool', 1.0, 0.0, 'grid', true),
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Events/VoltageSagActive',              'tomago_site01','voltage_sag_active',   'bool',  1.0, 0.0, 'grid', true),
    ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Events/LastEvent',                     'tomago_site01','last_event',           'string',1.0, 0.0, 'grid', true),
    -- Market (agl_market)
    ('[agl_market]AGL/Australia/NSW/Tomago/Site01/Market/RRP_AUD_per_MWh',                     'market', 'rrp_aud_per_mwh',        'AUD/MWh', 1.0, 0.0, 'market', true),
    ('[agl_market]AGL/Australia/NSW/Tomago/Site01/Market/PriceSpikeActive',                     'market', 'price_spike_active',      'bool',    1.0, 0.0, 'market', true),
    ('[agl_market]AGL/Australia/NSW/Tomago/Site01/Market/FCAS_ContingencyPrice_AUD_per_MWh',    'market', 'fcas_contingency_price',  'AUD/MWh', 1.0, 0.0, 'market', true),
    ('[agl_market]AGL/Australia/NSW/Tomago/Site01/Market/FCAS_RegPrice_AUD_per_MWh',            'market', 'fcas_reg_price',          'AUD/MWh', 1.0, 0.0, 'market', true),
    -- CMMS (agl_cmms)
    ('[agl_cmms]AGL/Australia/NSW/Tomago/Site01/CMMS/OpenWorkOrders',                  'cmms', 'open_work_orders',          'count',  1.0, 0.0, 'cmms', true),
    ('[agl_cmms]AGL/Australia/NSW/Tomago/Site01/CMMS/HighPriorityWorkOrders',          'cmms', 'high_priority_work_orders', 'count',  1.0, 0.0, 'cmms', true),
    ('[agl_cmms]AGL/Australia/NSW/Tomago/Site01/CMMS/PlannedOutageActive',             'cmms', 'planned_outage_active',     'bool',   1.0, 0.0, 'cmms', true),
    ('[agl_cmms]AGL/Australia/NSW/Tomago/Site01/CMMS/ForcedOutageActive',              'cmms', 'forced_outage_active',      'bool',   1.0, 0.0, 'cmms', true),
    ('[agl_cmms]AGL/Australia/NSW/Tomago/Site01/CMMS/LastWorkOrder',                   'cmms', 'last_work_order',           'string', 1.0, 0.0, 'cmms', true)
  AS defaults(tag_path, asset_id, signal_name, unit, scale, offset, source_domain, active)
) AS source
ON target.tag_path = source.tag_path
WHEN NOT MATCHED THEN INSERT *;

-- 4. Service Principal grants for Zerobus connector + app
--    Set SP_APPLICATION_ID env or replace __SP_APPLICATION_ID__ in this file.
GRANT USE CATALOG ON CATALOG __CATALOG__ TO `__SP_APPLICATION_ID__`;
GRANT USE SCHEMA ON SCHEMA __CATALOG__.__SCHEMA__ TO `__SP_APPLICATION_ID__`;
GRANT MODIFY, SELECT ON TABLE __CATALOG__.__SCHEMA__.raw_tags TO `__SP_APPLICATION_ID__`;
GRANT MODIFY, SELECT ON TABLE __CATALOG__.__SCHEMA__.asset_templates TO `__SP_APPLICATION_ID__`;
GRANT MODIFY, SELECT ON TABLE __CATALOG__.__SCHEMA__.template_attributes TO `__SP_APPLICATION_ID__`;
GRANT MODIFY, SELECT ON TABLE __CATALOG__.__SCHEMA__.asset_hierarchy TO `__SP_APPLICATION_ID__`;
GRANT MODIFY, SELECT ON TABLE __CATALOG__.__SCHEMA__.asset_attribute_values TO `__SP_APPLICATION_ID__`;
GRANT MODIFY, SELECT ON TABLE __CATALOG__.__SCHEMA__.sdt_config TO `__SP_APPLICATION_ID__`;
GRANT READ VOLUME ON VOLUME __CATALOG__.__SCHEMA__.wheels TO `__SP_APPLICATION_ID__`;
-- silver_asset_registry grant lives in pipelines/sql/setup_asset_framework.sql
-- so it runs after the view is created.
GRANT MODIFY, SELECT ON TABLE __CATALOG__.__SCHEMA__.silver_signal_mapping TO `__SP_APPLICATION_ID__`;
