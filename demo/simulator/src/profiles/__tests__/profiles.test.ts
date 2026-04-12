import { describe, it, expect } from 'vitest';
import windProfile from '../wind-turbine.json';
import batteryProfile from '../battery-bess.json';

interface TagProfile {
  name: string;
  unit: string;
  min: number;
  max: number;
  typical: number;
  noise_factor: number;
  update_frequency_ms: number;
  comp_dev: number;
  comp_dev_percent: number;
  comp_max_seconds: number;
  comp_min_seconds: number;
  pattern: string;
}

interface AssetProfile {
  asset_type: string;
  tags: TagProfile[];
}

const WIND_REQUIRED_TAGS = [
  'generator/speed_rpm',
  'generator/power_kw',
  'generator/torque_nm',
  'rotor/blade_pitch_deg',
  'rotor/wind_speed_ms',
  'rotor/rotor_rpm',
  'nacelle/yaw_angle_deg',
  'nacelle/temperature_c',
  'grid/voltage_v',
  'grid/frequency_hz',
  'grid/reactive_power_kvar',
  'status/operational_state',
  'status/alarm_code',
  'turbine/mode',
  'grid/fault_detected',
];

const BATTERY_REQUIRED_TAGS = [
  'battery/soc_pct',
  'battery/soh_pct',
  'battery/voltage_v',
  'battery/current_a',
  'battery/temperature_c',
  'battery/charge_rate_kw',
  'battery/discharge_rate_kw',
  'inverter/power_kw',
  'inverter/frequency_hz',
  'inverter/efficiency_pct',
  'thermal/coolant_temp_c',
  'thermal/ambient_temp_c',
  'status/operational_state',
  'status/alarm_code',
  'battery/mode',
  'cooling/active',
];

const REQUIRED_FIELDS = [
  'name',
  'unit',
  'min',
  'max',
  'typical',
  'noise_factor',
  'update_frequency_ms',
  'comp_dev',
  'comp_dev_percent',
  'comp_max_seconds',
  'comp_min_seconds',
];

describe('Asset tag profiles', () => {
  it('wind profile has all 15 required tags', () => {
    const profile = windProfile as AssetProfile;
    expect(profile.tags.length).toBe(15);
    const tagNames = profile.tags.map((t) => t.name);
    for (const required of WIND_REQUIRED_TAGS) {
      expect(tagNames).toContain(required);
    }
  });

  it('battery profile has all required tags', () => {
    const profile = batteryProfile as AssetProfile;
    expect(profile.tags.length).toBe(16);
    const tagNames = profile.tags.map((t) => t.name);
    for (const required of BATTERY_REQUIRED_TAGS) {
      expect(tagNames).toContain(required);
    }
  });

  it('each tag has all required fields', () => {
    const profiles = [windProfile, batteryProfile] as AssetProfile[];
    for (const profile of profiles) {
      for (const tag of profile.tags) {
        for (const field of REQUIRED_FIELDS) {
          expect(
            tag,
            `Tag "${tag.name}" in ${profile.asset_type} missing field "${field}"`,
          ).toHaveProperty(field);
        }
      }
    }
  });

  it('min < max for all numeric tags', () => {
    const profiles = [windProfile, batteryProfile] as AssetProfile[];
    for (const profile of profiles) {
      for (const tag of profile.tags) {
        expect(
          tag.min,
          `Tag "${tag.name}" in ${profile.asset_type}: min (${tag.min}) should be < max (${tag.max})`,
        ).toBeLessThan(tag.max);
      }
    }
  });
});
