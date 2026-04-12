-- Seed asset registry + signal mapping for the AGL Tomago BESS demo.
-- Assumes tag paths from examples/agl_tomago_bess_site01 and providers:
-- agl_bess, agl_grid, agl_market, agl_cmms

-- Assets
INSERT INTO agl_ignition.ot.silver_asset_registry (asset_id, parent_asset_id, asset_type, site, display_name, active)
VALUES
  ('tomago_site01', NULL, 'SITE', 'Tomago', 'Tomago Battery - Site01', true),
  ('bess01', 'tomago_site01', 'BESS', 'Tomago', 'BESS01 (500MW/2000MWh)', true),
  ('substation01', 'tomago_site01', 'SUBSTATION', 'Tomago', 'Substation01 / POI', true),
  ('market', 'tomago_site01', 'MARKET', 'Tomago', 'NEM / Price', true),
  ('cmms', 'tomago_site01', 'CMMS', 'Tomago', 'Maintenance / Work Orders', true);

-- Mapping helper note:
-- Use full tag_path strings (matches connector output exactly).

-- BESS telemetry (agl_bess)
INSERT INTO agl_ignition.ot.silver_signal_mapping
  (tag_path, asset_id, signal_name, unit, scale, offset, source_domain, active)
VALUES
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/SoC_pct', 'bess01', 'soc_pct', '%', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/SoH_pct', 'bess01', 'soh_pct', '%', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/EnergyAvailable_MWh', 'bess01', 'energy_available_mwh', 'MWh', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/ActivePower_MW', 'bess01', 'bess_active_power_mw', 'MW', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/ReactivePower_MVAr', 'bess01', 'bess_reactive_power_mvar', 'MVAr', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/Mode', 'bess01', 'mode', 'enum', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/DerateActive', 'bess01', 'derate_active', 'bool', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Telemetry/DerateReason', 'bess01', 'derate_reason', 'string', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Thermal/AmbientTemp_C', 'bess01', 'ambient_temp_c', 'C', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Thermal/HVAC_Running', 'bess01', 'hvac_running', 'bool', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Thermal/MaxRackTemp_C', 'bess01', 'max_rack_temp_c', 'C', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Limits/MaxCharge_MW', 'bess01', 'max_charge_mw', 'MW', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Limits/MaxDischarge_MW', 'bess01', 'max_discharge_mw', 'MW', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Alarms/AlarmCount', 'bess01', 'alarm_count', 'count', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Alarms/CriticalAlarmActive', 'bess01', 'critical_alarm_active', 'bool', 1.0, 0.0, 'bess', true),
  ('[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/Alarms/LastAlarm', 'bess01', 'last_alarm', 'string', 1.0, 0.0, 'bess', true);

-- Grid / dispatch (agl_grid)
INSERT INTO agl_ignition.ot.silver_signal_mapping
  (tag_path, asset_id, signal_name, unit, scale, offset, source_domain, active)
VALUES
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Substation01/POI/ExportPower_MW', 'substation01', 'poi_export_mw', 'MW', 1.0, 0.0, 'grid', true),
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Substation01/POI/ImportPower_MW', 'substation01', 'poi_import_mw', 'MW', 1.0, 0.0, 'grid', true),
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Substation01/POI/NetPower_MW', 'substation01', 'poi_net_mw', 'MW', 1.0, 0.0, 'grid', true),
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Substation01/POI/Voltage_kV', 'substation01', 'poi_voltage_kv', 'kV', 1.0, 0.0, 'grid', true),
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Substation01/POI/Frequency_Hz', 'substation01', 'poi_frequency_hz', 'Hz', 1.0, 0.0, 'grid', true),
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Dispatch/TargetNetPower_MW', 'tomago_site01', 'dispatch_target_mw', 'MW', 1.0, 0.0, 'grid', true),
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Dispatch/ConstraintActive', 'tomago_site01', 'constraint_active', 'bool', 1.0, 0.0, 'grid', true),
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Dispatch/ConstraintReason', 'tomago_site01', 'constraint_reason', 'string', 1.0, 0.0, 'grid', true),
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Dispatch/Curtailment_pct', 'tomago_site01', 'curtailment_pct', '%', 1.0, 0.0, 'grid', true),
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Dispatch/FCAS_Enabled', 'tomago_site01', 'fcas_enabled', 'bool', 1.0, 0.0, 'grid', true),
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Events/FrequencyEventActive', 'tomago_site01', 'frequency_event_active', 'bool', 1.0, 0.0, 'grid', true),
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Events/VoltageSagActive', 'tomago_site01', 'voltage_sag_active', 'bool', 1.0, 0.0, 'grid', true),
  ('[agl_grid]AGL/Australia/NSW/Tomago/Site01/Events/LastEvent', 'tomago_site01', 'last_event', 'string', 1.0, 0.0, 'grid', true);

-- Market (agl_market)
INSERT INTO agl_ignition.ot.silver_signal_mapping
  (tag_path, asset_id, signal_name, unit, scale, offset, source_domain, active)
VALUES
  ('[agl_market]AGL/Australia/NSW/Tomago/Site01/Market/RRP_AUD_per_MWh', 'market', 'rrp_aud_per_mwh', 'AUD/MWh', 1.0, 0.0, 'market', true),
  ('[agl_market]AGL/Australia/NSW/Tomago/Site01/Market/PriceSpikeActive', 'market', 'price_spike_active', 'bool', 1.0, 0.0, 'market', true),
  ('[agl_market]AGL/Australia/NSW/Tomago/Site01/Market/FCAS_ContingencyPrice_AUD_per_MWh', 'market', 'fcas_contingency_price', 'AUD/MWh', 1.0, 0.0, 'market', true),
  ('[agl_market]AGL/Australia/NSW/Tomago/Site01/Market/FCAS_RegPrice_AUD_per_MWh', 'market', 'fcas_reg_price', 'AUD/MWh', 1.0, 0.0, 'market', true);

-- CMMS (agl_cmms)
INSERT INTO agl_ignition.ot.silver_signal_mapping
  (tag_path, asset_id, signal_name, unit, scale, offset, source_domain, active)
VALUES
  ('[agl_cmms]AGL/Australia/NSW/Tomago/Site01/CMMS/OpenWorkOrders', 'cmms', 'open_work_orders', 'count', 1.0, 0.0, 'cmms', true),
  ('[agl_cmms]AGL/Australia/NSW/Tomago/Site01/CMMS/HighPriorityWorkOrders', 'cmms', 'high_priority_work_orders', 'count', 1.0, 0.0, 'cmms', true),
  ('[agl_cmms]AGL/Australia/NSW/Tomago/Site01/CMMS/PlannedOutageActive', 'cmms', 'planned_outage_active', 'bool', 1.0, 0.0, 'cmms', true),
  ('[agl_cmms]AGL/Australia/NSW/Tomago/Site01/CMMS/ForcedOutageActive', 'cmms', 'forced_outage_active', 'bool', 1.0, 0.0, 'cmms', true),
  ('[agl_cmms]AGL/Australia/NSW/Tomago/Site01/CMMS/LastWorkOrder', 'cmms', 'last_work_order', 'string', 1.0, 0.0, 'cmms', true);

