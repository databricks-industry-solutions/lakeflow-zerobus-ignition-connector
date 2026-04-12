import { describe, it, expect } from 'vitest';
import {
  generateSinusoidal,
  generateStep,
  generateRandomWalk,
  generateAlarm,
  TagValueGenerator,
} from '../generator.js';

describe('Value generation patterns', () => {
  it('sinusoidal pattern stays in bounds', () => {
    const values: number[] = [];
    for (let i = 0; i < 100; i++) {
      values.push(generateSinusoidal(0, 100, 0.02, i, 50));
    }
    for (const v of values) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
  });

  it('step function pattern produces steps', () => {
    const values: number[] = [];
    let state = 50;
    for (let i = 0; i < 1000; i++) {
      const result = generateStep(0, 100, state, i);
      values.push(result.value);
      state = result.state;
    }
    // Find distinct plateaus - count unique rounded values
    const rounded = values.map((v) => Math.round(v));
    const unique = new Set(rounded);
    expect(unique.size).toBeGreaterThanOrEqual(2);
  });

  it('random walk stays in bounds', () => {
    const values: number[] = [];
    let prev = 50;
    for (let i = 0; i < 1000; i++) {
      const v = generateRandomWalk(0, 100, 0.02, prev);
      values.push(v);
      prev = v;
    }
    for (const v of values) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
  });

  it('generator respects interval', async () => {
    const gen = new TagValueGenerator({
      name: 'test/tag',
      unit: 'unit',
      min: 0,
      max: 100,
      typical: 50,
      noise_factor: 0.01,
      update_frequency_ms: 100,
      pattern: 'sinusoidal',
      comp_dev: 1,
      comp_dev_percent: 1,
      comp_max_seconds: 600,
      comp_min_seconds: 0,
    });

    const timestamps: number[] = [];

    // Collect 5 values
    for (let i = 0; i < 5; i++) {
      const event = gen.next();
      timestamps.push(event.eventTimestamp.getTime());
      if (i < 4) {
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
    }

    // Check that timestamps are approximately 100ms apart (within 80ms tolerance)
    for (let i = 1; i < timestamps.length; i++) {
      const diff = timestamps[i] - timestamps[i - 1];
      expect(diff).toBeGreaterThanOrEqual(20); // Allow for some timing variance
      expect(diff).toBeLessThanOrEqual(250);
    }

    // Total elapsed should be reasonable
    const elapsed = timestamps[timestamps.length - 1] - timestamps[0];
    expect(elapsed).toBeGreaterThanOrEqual(200);
  });

  it('alarm pattern produces mostly zeros with occasional spikes', () => {
    const values: number[] = [];
    for (let i = 0; i < 1000; i++) {
      values.push(generateAlarm(0, 10));
    }
    // Most values should be 0 (no alarm)
    const zeros = values.filter((v) => v === 0);
    expect(zeros.length).toBeGreaterThan(900); // ~99.5% should be 0
    // All values should be in bounds
    for (const v of values) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(10);
    }
  });
});

describe('TagValueGenerator patterns', () => {
  const baseConfig = {
    name: 'test/tag',
    unit: 'unit',
    min: 0,
    max: 100,
    typical: 50,
    noise_factor: 0.02,
    update_frequency_ms: 100,
    comp_dev: 1,
    comp_dev_percent: 1,
    comp_max_seconds: 600,
    comp_min_seconds: 0,
  };

  it('step pattern generator maintains state across calls', () => {
    const gen = new TagValueGenerator({ ...baseConfig, pattern: 'step' });
    const values: number[] = [];
    for (let i = 0; i < 1000; i++) {
      const event = gen.next('asset1');
      values.push(event.tagValue);
    }
    // Values should be in bounds
    for (const v of values) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
    // Should have some variety (steps happen ~1% of the time)
    const unique = new Set(values.map((v) => Math.round(v)));
    expect(unique.size).toBeGreaterThanOrEqual(2);
  });

  it('random_walk pattern generator maintains state across calls', () => {
    const gen = new TagValueGenerator({ ...baseConfig, pattern: 'random_walk' });
    const values: number[] = [];
    for (let i = 0; i < 100; i++) {
      const event = gen.next('asset1');
      values.push(event.tagValue);
    }
    // Values should be in bounds
    for (const v of values) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
    // Values should vary (random walk)
    const unique = new Set(values.map((v) => Math.round(v * 10) / 10));
    expect(unique.size).toBeGreaterThan(1);
  });

  it('alarm pattern generator produces mostly zeros', () => {
    const gen = new TagValueGenerator({ ...baseConfig, pattern: 'alarm' });
    const values: number[] = [];
    for (let i = 0; i < 1000; i++) {
      const event = gen.next('asset1');
      values.push(event.tagValue);
    }
    // Most should be 0
    const zeros = values.filter((v) => v === 0);
    expect(zeros.length).toBeGreaterThan(900);
  });

  it('unknown pattern falls back to sinusoidal', () => {
    const gen = new TagValueGenerator({ ...baseConfig, pattern: 'unknown_pattern' });
    const values: number[] = [];
    for (let i = 0; i < 100; i++) {
      const event = gen.next('asset1');
      values.push(event.tagValue);
    }
    // Values should be in bounds (sinusoidal behavior)
    for (const v of values) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
  });

  it('next() returns correct event structure', () => {
    const gen = new TagValueGenerator({ ...baseConfig, pattern: 'sinusoidal' });
    const event = gen.next('test_asset', new Date('2026-02-13T12:00:00Z'));

    expect(event).toHaveProperty('eventTimestamp');
    expect(event).toHaveProperty('assetId', 'test_asset');
    expect(event).toHaveProperty('tagName', 'test/tag');
    expect(event).toHaveProperty('tagValue');
    expect(event).toHaveProperty('quality', 192);
    expect(event.tagValue).toBeGreaterThanOrEqual(0);
    expect(event.tagValue).toBeLessThanOrEqual(100);
  });
});
