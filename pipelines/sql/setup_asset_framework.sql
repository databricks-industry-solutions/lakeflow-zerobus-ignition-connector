-- Asset Framework tables for __CATALOG__.__SCHEMA__
-- Replace __CATALOG__ and __SCHEMA__ (e.g. agl_demo, ot) before running.
-- Replaces AF with open Delta Lake asset management
--
-- This is the single source of truth for asset metadata.
-- The old ot.assets table is retired - use asset_hierarchy instead.

-- 1. Asset templates - standardised attribute definitions per asset type
CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.asset_templates (
  template_id STRING NOT NULL,
  template_name STRING NOT NULL,
  description STRING,
  base_asset_type STRING NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT asset_templates_pk PRIMARY KEY (template_id)
);

-- 2. Template attributes - individual attribute definitions within a template
CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.template_attributes (
  attribute_id STRING NOT NULL,
  template_id STRING NOT NULL,
  attribute_name STRING NOT NULL,
  data_type STRING NOT NULL,  -- DOUBLE, STRING, BOOLEAN, INT, TIMESTAMP
  unit STRING,
  default_value STRING,
  is_required BOOLEAN DEFAULT false,
  sort_order INT DEFAULT 0,
  tag_pattern STRING              COMMENT 'Tag name from parsed_tags to bind for live values',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT template_attributes_pk PRIMARY KEY (attribute_id),
  CONSTRAINT template_attributes_fk FOREIGN KEY (template_id) REFERENCES __CATALOG__.__SCHEMA__.asset_templates(template_id)
);

-- Idempotent column add for existing deployments that lack tag_pattern.
-- run_setup_sql.py gracefully ignores COLUMN_ALREADY_EXISTS errors on ADD COLUMN.
ALTER TABLE __CATALOG__.__SCHEMA__.template_attributes
ADD COLUMN tag_pattern STRING COMMENT 'Tag name from parsed_tags to bind for live values';

-- 3. Asset hierarchy - navigable parent-child tree of assets
--    Also serves as the asset metadata table (replaces ot.assets).
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
);

-- 4. Asset attribute values - actual attribute values for each asset
CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.asset_attribute_values (
  asset_id STRING NOT NULL,
  attribute_id STRING NOT NULL,
  value STRING,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT asset_attribute_values_pk PRIMARY KEY (asset_id, attribute_id),
  CONSTRAINT asset_attr_values_asset_fk FOREIGN KEY (asset_id) REFERENCES __CATALOG__.__SCHEMA__.asset_hierarchy(asset_id),
  CONSTRAINT asset_attr_values_attr_fk FOREIGN KEY (attribute_id) REFERENCES __CATALOG__.__SCHEMA__.template_attributes(attribute_id)
);

-- =========================================================================
-- Seed data: Templates
-- =========================================================================

MERGE INTO __CATALOG__.__SCHEMA__.asset_templates AS t
USING (
  SELECT * FROM (VALUES
    ('tpl_bess',      'BESS',           'Battery Energy Storage System template with charge/discharge metrics', 'battery_bess'),
    ('tpl_wind',      'Wind Turbine',   'Wind turbine template with rotor and generator attributes',            'wind_turbine'),
    ('tpl_substation','Substation',      'Electrical substation with transformer and breaker attributes',        'substation'),
    ('tpl_inverter',  'Inverter',        'DC-AC inverter for solar or battery systems',                         'inverter')
  ) AS vals(template_id, template_name, description, base_asset_type)
) AS s
ON t.template_id = s.template_id
WHEN NOT MATCHED THEN INSERT (template_id, template_name, description, base_asset_type)
VALUES (s.template_id, s.template_name, s.description, s.base_asset_type);

-- =========================================================================
-- Seed data: Template attributes
-- =========================================================================

MERGE INTO __CATALOG__.__SCHEMA__.template_attributes AS t
USING (
  SELECT * FROM (VALUES
    -- BESS attributes (tag_pattern references parsed_tags.tag_name for live binding)
    ('attr_bess_soc',       'tpl_bess', 'State of Charge',    'DOUBLE',  '%',    '50.0',  true,  1, 'telemetry/soc_pct'),
    ('attr_bess_soh',       'tpl_bess', 'State of Health',    'DOUBLE',  '%',    '100.0', true,  2, 'telemetry/soh_pct'),
    ('attr_bess_power',     'tpl_bess', 'Active Power',       'DOUBLE',  'MW',   '0.0',   true,  3, 'telemetry/activepower_mw'),
    ('attr_bess_voltage',   'tpl_bess', 'DC Bus Voltage',     'DOUBLE',  'V',    '800.0', false, 4, 'telemetry/dcvoltage_v'),
    ('attr_bess_temp',      'tpl_bess', 'Cell Temperature',   'DOUBLE',  'C',    '25.0',  false, 5, 'thermal/maxracktemp_c'),
    ('attr_bess_cycles',    'tpl_bess', 'Cycle Count',        'INT',     NULL,   '0',     false, 6, NULL),
    ('attr_bess_capacity',  'tpl_bess', 'Rated Capacity',     'DOUBLE',  'MWh',  '100.0', true,  7, 'telemetry/energyavailable_mwh'),
    ('attr_bess_mode',      'tpl_bess', 'Operating Mode',     'STRING',  NULL,   'IDLE',  true,  8, 'telemetry/mode'),
    -- Wind turbine attributes (no simulator tags yet)
    ('attr_wind_speed',     'tpl_wind', 'Wind Speed',         'DOUBLE',  'm/s',  '0.0',   true,  1, NULL),
    ('attr_wind_power',     'tpl_wind', 'Active Power',       'DOUBLE',  'MW',   '0.0',   true,  2, NULL),
    ('attr_wind_rpm',       'tpl_wind', 'Rotor RPM',          'DOUBLE',  'rpm',  '0.0',   true,  3, NULL),
    ('attr_wind_pitch',     'tpl_wind', 'Blade Pitch Angle',  'DOUBLE',  'deg',  '0.0',   false, 4, NULL),
    ('attr_wind_yaw',       'tpl_wind', 'Nacelle Yaw',        'DOUBLE',  'deg',  '0.0',   false, 5, NULL),
    ('attr_wind_gen_temp',  'tpl_wind', 'Generator Temp',     'DOUBLE',  'C',    '40.0',  false, 6, NULL),
    ('attr_wind_capacity',  'tpl_wind', 'Rated Capacity',     'DOUBLE',  'MW',   '3.0',   true,  7, NULL),
    ('attr_wind_status',    'tpl_wind', 'Turbine Status',     'STRING',  NULL,   'STOPPED', true, 8, NULL),
    -- Substation attributes (no simulator tags yet)
    ('attr_sub_voltage',    'tpl_substation', 'Bus Voltage',       'DOUBLE', 'kV',  '132.0', true,  1, NULL),
    ('attr_sub_current',    'tpl_substation', 'Bus Current',       'DOUBLE', 'A',   '0.0',   true,  2, NULL),
    ('attr_sub_frequency',  'tpl_substation', 'Grid Frequency',    'DOUBLE', 'Hz',  '50.0',  true,  3, NULL),
    ('attr_sub_power',      'tpl_substation', 'Active Power',      'DOUBLE', 'MVA', '0.0',   false, 4, NULL),
    ('attr_sub_tap',        'tpl_substation', 'Transformer Tap',   'INT',    NULL,  '5',     false, 5, NULL),
    ('attr_sub_breaker',    'tpl_substation', 'Breaker Status',    'BOOLEAN', NULL, 'true',  true,  6, NULL),
    -- Inverter attributes (no simulator tags yet)
    ('attr_inv_dc_voltage', 'tpl_inverter', 'DC Input Voltage',  'DOUBLE', 'V',   '800.0', true,  1, NULL),
    ('attr_inv_ac_voltage', 'tpl_inverter', 'AC Output Voltage', 'DOUBLE', 'V',   '415.0', true,  2, NULL),
    ('attr_inv_power',      'tpl_inverter', 'Output Power',      'DOUBLE', 'kW',  '0.0',   true,  3, NULL),
    ('attr_inv_efficiency', 'tpl_inverter', 'Efficiency',        'DOUBLE', '%',   '98.0',  false, 4, NULL),
    ('attr_inv_temp',       'tpl_inverter', 'Heatsink Temp',     'DOUBLE', 'C',   '35.0',  false, 5, NULL),
    ('attr_inv_status',     'tpl_inverter', 'Inverter Status',   'STRING', NULL,  'OFF',   true,  6, NULL)
  ) AS vals(attribute_id, template_id, attribute_name, data_type, unit, default_value, is_required, sort_order, tag_pattern)
) AS s
ON t.attribute_id = s.attribute_id
WHEN MATCHED THEN UPDATE SET tag_pattern = s.tag_pattern
WHEN NOT MATCHED THEN INSERT (attribute_id, template_id, attribute_name, data_type, unit, default_value, is_required, sort_order, tag_pattern)
VALUES (s.attribute_id, s.template_id, s.attribute_name, s.data_type, s.unit, s.default_value, s.is_required, s.sort_order, s.tag_pattern);

-- =========================================================================
-- Seed data: Asset hierarchy - AGL Fleet topology
--
-- 5 sites x 9 assets/site = 45 equipment nodes + 5 sites + 1 enterprise = 51 total
-- Asset IDs match what parsed_tags computes: LOWER(CONCAT(_p[3], '_', _p[5]))
--
-- Tag path structure from simulator:
--   [agl_bess]AGL/Australia/{state}/{location}/Site01/BESS{nn}/...
--   [agl_grid]AGL/Australia/{state}/{location}/Site01/Substation01/...
--   [agl_grid]AGL/Australia/{state}/{location}/Site01/Dispatch/...
--   [agl_grid]AGL/Australia/{state}/{location}/Site01/Events/...
--   [agl_market]AGL/Australia/{state}/{location}/Site01/Market/...
--   [agl_cmms]AGL/Australia/{state}/{location}/Site01/CMMS/...
-- =========================================================================

MERGE INTO __CATALOG__.__SCHEMA__.asset_hierarchy AS t
USING (
  SELECT * FROM (VALUES
    -- Enterprise root
    ('agl_enterprise',  NULL,              'AGL Energy',                'enterprise', NULL,             NULL,          'AGL Energy Ltd - Enterprise root',       NULL,  NULL,    NULL,    NULL),

    -- Tomago (Newcastle NSW)
    ('site_tomago',     'agl_enterprise',  'Tomago BESS Farm',          'site',       NULL,             'Tomago',      'Newcastle NSW - 4x 500MW BESS',         NULL,  -32.79,  151.86,  NULL),
    ('tomago_bess01',   'site_tomago',     'Tomago BESS01 (500MW)',     'battery_bess','tpl_bess',      'Tomago',      'BESS Unit 01',                          500.0, -32.79,  151.86,  23),
    ('tomago_bess02',   'site_tomago',     'Tomago BESS02 (500MW)',     'battery_bess','tpl_bess',      'Tomago',      'BESS Unit 02',                          500.0, -32.79,  151.86,  23),
    ('tomago_bess03',   'site_tomago',     'Tomago BESS03 (500MW)',     'battery_bess','tpl_bess',      'Tomago',      'BESS Unit 03',                          500.0, -32.79,  151.86,  23),
    ('tomago_bess04',   'site_tomago',     'Tomago BESS04 (500MW)',     'battery_bess','tpl_bess',      'Tomago',      'BESS Unit 04',                          500.0, -32.79,  151.86,  23),
    ('tomago_substation01','site_tomago',  'Tomago Substation01 / POI', 'grid_infrastructure','tpl_substation','Tomago','POI metering and protection',           NULL,  -32.79,  151.86,  8),
    ('tomago_dispatch', 'site_tomago',     'Tomago Dispatch Control',   'grid_infrastructure',NULL,     'Tomago',      'AEMO dispatch targets and constraints',  NULL,  -32.79,  151.86,  5),
    ('tomago_events',   'site_tomago',     'Tomago Grid Events',        'grid_infrastructure',NULL,     'Tomago',      'Frequency and voltage events',           NULL,  -32.79,  151.86,  3),
    ('tomago_market',   'site_tomago',     'Tomago NEM / Price',        'market_data', NULL,            'Tomago',      'NEM spot and FCAS prices',               NULL,  -32.79,  151.86,  4),
    ('tomago_cmms',     'site_tomago',     'Tomago Maintenance',        'maintenance', NULL,            'Tomago',      'Work orders and outage tracking',        NULL,  -32.79,  151.86,  5),

    -- Liddell (Hunter Valley NSW)
    ('site_liddell',    'agl_enterprise',  'Liddell BESS Farm',         'site',       NULL,             'Liddell',     'Hunter Valley NSW - 4x 500MW BESS',     NULL,  -32.37,  150.97,  NULL),
    ('liddell_bess01',  'site_liddell',    'Liddell BESS01 (500MW)',    'battery_bess','tpl_bess',      'Liddell',     'BESS Unit 01',                          500.0, -32.37,  150.97,  23),
    ('liddell_bess02',  'site_liddell',    'Liddell BESS02 (500MW)',    'battery_bess','tpl_bess',      'Liddell',     'BESS Unit 02',                          500.0, -32.37,  150.97,  23),
    ('liddell_bess03',  'site_liddell',    'Liddell BESS03 (500MW)',    'battery_bess','tpl_bess',      'Liddell',     'BESS Unit 03',                          500.0, -32.37,  150.97,  23),
    ('liddell_bess04',  'site_liddell',    'Liddell BESS04 (500MW)',    'battery_bess','tpl_bess',      'Liddell',     'BESS Unit 04',                          500.0, -32.37,  150.97,  23),
    ('liddell_substation01','site_liddell','Liddell Substation01 / POI','grid_infrastructure','tpl_substation','Liddell','POI metering and protection',          NULL,  -32.37,  150.97,  8),
    ('liddell_dispatch','site_liddell',    'Liddell Dispatch Control',  'grid_infrastructure',NULL,     'Liddell',     'AEMO dispatch targets and constraints',  NULL,  -32.37,  150.97,  5),
    ('liddell_events',  'site_liddell',    'Liddell Grid Events',       'grid_infrastructure',NULL,     'Liddell',     'Frequency and voltage events',           NULL,  -32.37,  150.97,  3),
    ('liddell_market',  'site_liddell',    'Liddell NEM / Price',       'market_data', NULL,            'Liddell',     'NEM spot and FCAS prices',               NULL,  -32.37,  150.97,  4),
    ('liddell_cmms',    'site_liddell',    'Liddell Maintenance',       'maintenance', NULL,            'Liddell',     'Work orders and outage tracking',        NULL,  -32.37,  150.97,  5),

    -- Broken Hill (Far west NSW)
    ('site_brokenhill', 'agl_enterprise',  'Broken Hill BESS Farm',     'site',       NULL,             'Broken Hill', 'Far west NSW - 4x 500MW BESS',          NULL,  -31.95,  141.45,  NULL),
    ('brokenhill_bess01','site_brokenhill','Broken Hill BESS01 (500MW)','battery_bess','tpl_bess',      'Broken Hill', 'BESS Unit 01',                          500.0, -31.95,  141.45,  23),
    ('brokenhill_bess02','site_brokenhill','Broken Hill BESS02 (500MW)','battery_bess','tpl_bess',      'Broken Hill', 'BESS Unit 02',                          500.0, -31.95,  141.45,  23),
    ('brokenhill_bess03','site_brokenhill','Broken Hill BESS03 (500MW)','battery_bess','tpl_bess',      'Broken Hill', 'BESS Unit 03',                          500.0, -31.95,  141.45,  23),
    ('brokenhill_bess04','site_brokenhill','Broken Hill BESS04 (500MW)','battery_bess','tpl_bess',      'Broken Hill', 'BESS Unit 04',                          500.0, -31.95,  141.45,  23),
    ('brokenhill_substation01','site_brokenhill','Broken Hill Substation01 / POI','grid_infrastructure','tpl_substation','Broken Hill','POI metering and protection', NULL, -31.95, 141.45, 8),
    ('brokenhill_dispatch','site_brokenhill','Broken Hill Dispatch Control','grid_infrastructure',NULL, 'Broken Hill', 'AEMO dispatch targets and constraints',  NULL,  -31.95,  141.45,  5),
    ('brokenhill_events','site_brokenhill','Broken Hill Grid Events',   'grid_infrastructure',NULL,     'Broken Hill', 'Frequency and voltage events',           NULL,  -31.95,  141.45,  3),
    ('brokenhill_market','site_brokenhill','Broken Hill NEM / Price',   'market_data', NULL,            'Broken Hill', 'NEM spot and FCAS prices',               NULL,  -31.95,  141.45,  4),
    ('brokenhill_cmms', 'site_brokenhill', 'Broken Hill Maintenance',   'maintenance', NULL,            'Broken Hill', 'Work orders and outage tracking',        NULL,  -31.95,  141.45,  5),

    -- Callide (Queensland)
    ('site_callide',    'agl_enterprise',  'Callide BESS Farm',         'site',       NULL,             'Callide',     'Central QLD - 4x 500MW BESS',           NULL,  -24.43,  150.97,  NULL),
    ('callide_bess01',  'site_callide',    'Callide BESS01 (500MW)',    'battery_bess','tpl_bess',      'Callide',     'BESS Unit 01',                          500.0, -24.43,  150.97,  23),
    ('callide_bess02',  'site_callide',    'Callide BESS02 (500MW)',    'battery_bess','tpl_bess',      'Callide',     'BESS Unit 02',                          500.0, -24.43,  150.97,  23),
    ('callide_bess03',  'site_callide',    'Callide BESS03 (500MW)',    'battery_bess','tpl_bess',      'Callide',     'BESS Unit 03',                          500.0, -24.43,  150.97,  23),
    ('callide_bess04',  'site_callide',    'Callide BESS04 (500MW)',    'battery_bess','tpl_bess',      'Callide',     'BESS Unit 04',                          500.0, -24.43,  150.97,  23),
    ('callide_substation01','site_callide','Callide Substation01 / POI','grid_infrastructure','tpl_substation','Callide','POI metering and protection',          NULL,  -24.43,  150.97,  8),
    ('callide_dispatch','site_callide',    'Callide Dispatch Control',  'grid_infrastructure',NULL,     'Callide',     'AEMO dispatch targets and constraints',  NULL,  -24.43,  150.97,  5),
    ('callide_events',  'site_callide',    'Callide Grid Events',       'grid_infrastructure',NULL,     'Callide',     'Frequency and voltage events',           NULL,  -24.43,  150.97,  3),
    ('callide_market',  'site_callide',    'Callide NEM / Price',       'market_data', NULL,            'Callide',     'NEM spot and FCAS prices',               NULL,  -24.43,  150.97,  4),
    ('callide_cmms',    'site_callide',    'Callide Maintenance',       'maintenance', NULL,            'Callide',     'Work orders and outage tracking',        NULL,  -24.43,  150.97,  5),

    -- Gladstone (Queensland)
    ('site_gladstone',  'agl_enterprise',  'Gladstone BESS Farm',       'site',       NULL,             'Gladstone',   'North QLD - 4x 500MW BESS',             NULL,  -23.85,  151.27,  NULL),
    ('gladstone_bess01','site_gladstone',  'Gladstone BESS01 (500MW)',  'battery_bess','tpl_bess',      'Gladstone',   'BESS Unit 01',                          500.0, -23.85,  151.27,  23),
    ('gladstone_bess02','site_gladstone',  'Gladstone BESS02 (500MW)',  'battery_bess','tpl_bess',      'Gladstone',   'BESS Unit 02',                          500.0, -23.85,  151.27,  23),
    ('gladstone_bess03','site_gladstone',  'Gladstone BESS03 (500MW)',  'battery_bess','tpl_bess',      'Gladstone',   'BESS Unit 03',                          500.0, -23.85,  151.27,  23),
    ('gladstone_bess04','site_gladstone',  'Gladstone BESS04 (500MW)',  'battery_bess','tpl_bess',      'Gladstone',   'BESS Unit 04',                          500.0, -23.85,  151.27,  23),
    ('gladstone_substation01','site_gladstone','Gladstone Substation01 / POI','grid_infrastructure','tpl_substation','Gladstone','POI metering and protection',  NULL,  -23.85,  151.27,  8),
    ('gladstone_dispatch','site_gladstone','Gladstone Dispatch Control','grid_infrastructure',NULL,     'Gladstone',   'AEMO dispatch targets and constraints',  NULL,  -23.85,  151.27,  5),
    ('gladstone_events','site_gladstone',  'Gladstone Grid Events',     'grid_infrastructure',NULL,     'Gladstone',   'Frequency and voltage events',           NULL,  -23.85,  151.27,  3),
    ('gladstone_market','site_gladstone',  'Gladstone NEM / Price',     'market_data', NULL,            'Gladstone',   'NEM spot and FCAS prices',               NULL,  -23.85,  151.27,  4),
    ('gladstone_cmms',  'site_gladstone',  'Gladstone Maintenance',     'maintenance', NULL,            'Gladstone',   'Work orders and outage tracking',        NULL,  -23.85,  151.27,  5)
  ) AS vals(asset_id, parent_asset_id, asset_name, asset_type, template_id, site_name, description, capacity_mw, latitude, longitude, tag_count)
) AS s
ON t.asset_id = s.asset_id
WHEN NOT MATCHED THEN INSERT (asset_id, parent_asset_id, asset_name, asset_type, template_id, site_name, description, capacity_mw, latitude, longitude, tag_count)
VALUES (s.asset_id, s.parent_asset_id, s.asset_name, s.asset_type, s.template_id, s.site_name, s.description, s.capacity_mw, s.latitude, s.longitude, s.tag_count);

-- =========================================================================
-- Seed data: Apply template defaults to assets that have templates
-- =========================================================================

MERGE INTO __CATALOG__.__SCHEMA__.asset_attribute_values AS t
USING (
  SELECT h.asset_id, ta.attribute_id, ta.default_value AS value
  FROM __CATALOG__.__SCHEMA__.asset_hierarchy h
  JOIN __CATALOG__.__SCHEMA__.template_attributes ta ON h.template_id = ta.template_id
  WHERE h.template_id IS NOT NULL
) AS s
ON t.asset_id = s.asset_id AND t.attribute_id = s.attribute_id
WHEN NOT MATCHED THEN INSERT (asset_id, attribute_id, value)
VALUES (s.asset_id, s.attribute_id, s.value);

-- ---------------------------------------------------------------------------
-- silver_asset_registry VIEW (compatibility layer)
-- ---------------------------------------------------------------------------
-- Replaces the old standalone silver_asset_registry TABLE with a view that
-- reads from asset_hierarchy. This makes asset_hierarchy the single source of
-- truth - CRUD changes here flow through to health_scores and revenue_risk.
--
-- The CASE expression maps asset_hierarchy types to the uppercase types that
-- the SDP pipeline expects (revenue_risk.py checks for 'BESS', 'SUBSTATION').
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW __CATALOG__.__SCHEMA__.silver_asset_registry AS
SELECT
  h.asset_id,
  h.asset_name,
  CASE
    WHEN h.asset_type = 'battery_bess' THEN 'BESS'
    WHEN h.asset_type = 'grid_infrastructure' AND LOWER(h.asset_id) LIKE '%substation%' THEN 'SUBSTATION'
    WHEN h.asset_type = 'grid_infrastructure' THEN 'GRID'
    WHEN h.asset_type = 'market_data' THEN 'MARKET'
    WHEN h.asset_type = 'maintenance' THEN 'CMMS'
    WHEN h.asset_type = 'site' THEN 'SITE'
    ELSE UPPER(h.asset_type)
  END AS asset_type,
  h.site_name,
  h.capacity_mw,
  h.latitude,
  h.longitude,
  h.active
FROM __CATALOG__.__SCHEMA__.asset_hierarchy h
WHERE h.asset_type NOT IN ('enterprise');

-- ---------------------------------------------------------------------------
-- silver_signal_mapping_normalized VIEW
-- ---------------------------------------------------------------------------
-- Normalizes legacy mapping rows to hierarchy-compatible IDs and tag paths.
-- This lets UI/API joins rely on one stable key shape:
--   hierarchy_asset_id = lower(location + '_' + asset)
--   normalized_tag_name = lower(subsystem/signal)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW __CATALOG__.__SCHEMA__.silver_signal_mapping_normalized AS
WITH parsed AS (
  SELECT
    m.*,
    SPLIT(REGEXP_REPLACE(m.tag_path, '^\\[[^\\]]+\\]', ''), '/') AS _p
  FROM __CATALOG__.__SCHEMA__.silver_signal_mapping m
)
SELECT
  tag_path,
  asset_id AS mapped_asset_id,
  signal_name,
  unit,
  scale,
  offset,
  source_domain,
  active,
  CASE
    WHEN tag_path RLIKE '^\\[agl_' AND SIZE(_p) >= 6 THEN LOWER(CONCAT(_p[3], '_', _p[5]))
    WHEN asset_id IS NOT NULL THEN LOWER(asset_id)
    ELSE NULL
  END AS hierarchy_asset_id,
  CASE
    WHEN tag_path RLIKE '^\\[agl_' AND SIZE(_p) >= 7 THEN LOWER(ARRAY_JOIN(SLICE(_p, 7, SIZE(_p) - 6), '/'))
    WHEN signal_name IS NOT NULL THEN LOWER(signal_name)
    ELSE LOWER(tag_path)
  END AS normalized_tag_name
FROM parsed;

-- Grant after the view exists (placeholder replaced by run_setup_sql.py).
GRANT SELECT ON VIEW __CATALOG__.__SCHEMA__.silver_asset_registry TO `__SP_APPLICATION_ID__`;
GRANT SELECT ON VIEW __CATALOG__.__SCHEMA__.silver_signal_mapping_normalized TO `__SP_APPLICATION_ID__`;
