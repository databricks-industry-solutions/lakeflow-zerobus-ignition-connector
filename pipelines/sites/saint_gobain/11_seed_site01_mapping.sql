-- Seed asset registry + signal mapping for Saint-Gobain Site01 demo

MERGE INTO ignition_demo.ot.silver_asset_registry t
USING (
  SELECT 'sg_site01' AS asset_id, NULL AS parent_asset_id, 'site' AS asset_type, 'Site01' AS site, 'Saint-Gobain Site01 (Demo)' AS display_name, true AS active
  UNION ALL SELECT 'sg_furnace', 'sg_site01', 'furnace', 'Site01', 'Furnace', true
  UNION ALL SELECT 'sg_conveyor', 'sg_site01', 'conveyor', 'Site01', 'Conveyor', true
  UNION ALL SELECT 'sg_cut', 'sg_site01', 'cutting_station', 'Site01', 'Cutting Station', true
) s
ON t.asset_id = s.asset_id
WHEN MATCHED THEN UPDATE SET
  t.parent_asset_id = s.parent_asset_id,
  t.asset_type = s.asset_type,
  t.site = s.site,
  t.display_name = s.display_name,
  t.active = s.active
WHEN NOT MATCHED THEN INSERT *;

MERGE INTO ignition_demo.ot.silver_signal_mapping t
USING (
  -- Plant telemetry ([sg])
  SELECT '[sg]SG/Site01/Furnace/Temperature_Melting_C' AS tag_path, 'sg_furnace' AS asset_id, 'melting_temp' AS signal_name, 'C' AS unit, 1.0 AS scale, 0.0 AS offset, 'plant' AS source_domain, true AS active
  UNION ALL SELECT '[sg]SG/Site01/Furnace/Temperature_Forming_C', 'sg_furnace', 'forming_temp', 'C', 1.0, 0.0, 'plant', true
  UNION ALL SELECT '[sg]SG/Site01/Furnace/Pressure_Chamber_bar', 'sg_furnace', 'pressure', 'bar', 1.0, 0.0, 'plant', true
  UNION ALL SELECT '[sg]SG/Site01/Furnace/Gas_Flow_m3h', 'sg_furnace', 'gas_flow', 'm3/h', 1.0, 0.0, 'plant', true
  UNION ALL SELECT '[sg]SG/Site01/Furnace/Glass_Thickness_mm', 'sg_furnace', 'thickness', 'mm', 1.0, 0.0, 'plant', true

  UNION ALL SELECT '[sg]SG/Site01/Conveyor/Speed_mpm', 'sg_conveyor', 'speed', 'm/min', 1.0, 0.0, 'plant', true
  UNION ALL SELECT '[sg]SG/Site01/Conveyor/Load_kg', 'sg_conveyor', 'load', 'kg', 1.0, 0.0, 'plant', true
  UNION ALL SELECT '[sg]SG/Site01/Conveyor/Vibration_mms', 'sg_conveyor', 'vibration', 'mm/s', 1.0, 0.0, 'plant', true

  UNION ALL SELECT '[sg]SG/Site01/CuttingStation/Cut_Count', 'sg_cut', 'cut_count', 'count', 1.0, 0.0, 'plant', true
  UNION ALL SELECT '[sg]SG/Site01/CuttingStation/Blade_Temp_C', 'sg_cut', 'blade_temp', 'C', 1.0, 0.0, 'plant', true
  UNION ALL SELECT '[sg]SG/Site01/CuttingStation/Quality_Score', 'sg_cut', 'quality_score', 'score', 1.0, 0.0, 'plant', true

  UNION ALL SELECT '[sg]SG/Site01/KPIs/Throughput_units_per_min', 'sg_site01', 'throughput', 'units/min', 1.0, 0.0, 'plant', true
  UNION ALL SELECT '[sg]SG/Site01/KPIs/ScrapRate_pct', 'sg_site01', 'scrap_rate', '%', 1.0, 0.0, 'plant', true

  -- Grid/dispatch ([sg_grid])
  UNION ALL SELECT '[sg_grid]SG/Site01/Dispatch/TargetRate_units_per_min', 'sg_site01', 'target_throughput', 'units/min', 1.0, 0.0, 'grid', true
  UNION ALL SELECT '[sg_grid]SG/Site01/Dispatch/Curtailment_pct', 'sg_site01', 'curtailment', '%', 1.0, 0.0, 'grid', true
  UNION ALL SELECT '[sg_grid]SG/Site01/Energy/GasPrice_EUR_per_GJ', 'sg_site01', 'gas_price', 'EUR/GJ', 1.0, 0.0, 'grid', true
  UNION ALL SELECT '[sg_grid]SG/Site01/Energy/ElectricityPrice_EUR_per_MWh', 'sg_site01', 'elec_price', 'EUR/MWh', 1.0, 0.0, 'grid', true

  -- CMMS ([sg_cmms])
  UNION ALL SELECT '[sg_cmms]SG/Site01/WorkOrders/ActiveCount', 'sg_site01', 'active_work_orders', 'count', 1.0, 0.0, 'cmms', true
  UNION ALL SELECT '[sg_cmms]SG/Site01/WorkOrders/HighPriorityCount', 'sg_site01', 'high_priority_work_orders', 'count', 1.0, 0.0, 'cmms', true
  UNION ALL SELECT '[sg_cmms]SG/Site01/Assets/Furnace/ForcedOutage', 'sg_furnace', 'forced_outage', 'bool', 1.0, 0.0, 'cmms', true
  UNION ALL SELECT '[sg_cmms]SG/Site01/Assets/Conveyor/ForcedOutage', 'sg_conveyor', 'forced_outage', 'bool', 1.0, 0.0, 'cmms', true
  UNION ALL SELECT '[sg_cmms]SG/Site01/Assets/CuttingStation/ForcedOutage', 'sg_cut', 'forced_outage', 'bool', 1.0, 0.0, 'cmms', true

  -- Forecast ([sg_forecast])
  UNION ALL SELECT '[sg_forecast]SG/Site01/Forecast/H01/Throughput_units_per_min', 'sg_site01', 'throughput_forecast_h01', 'units/min', 1.0, 0.0, 'forecast', true
  UNION ALL SELECT '[sg_forecast]SG/Site01/Forecast/H01/ScrapRate_pct', 'sg_site01', 'scrap_forecast_h01', '%', 1.0, 0.0, 'forecast', true
  UNION ALL SELECT '[sg_forecast]SG/Site01/Forecast/H01/Confidence_pct', 'sg_site01', 'forecast_confidence_h01', '%', 1.0, 0.0, 'forecast', true
) s
ON t.tag_path = s.tag_path
WHEN MATCHED THEN UPDATE SET
  t.asset_id = s.asset_id,
  t.signal_name = s.signal_name,
  t.unit = s.unit,
  t.scale = s.scale,
  t.offset = s.offset,
  t.source_domain = s.source_domain,
  t.active = s.active
WHEN NOT MATCHED THEN INSERT *;


