import { describe, it, expect } from 'vitest';
import { generateTagValue } from '../generator.js';
import { createPublisher } from '../publisher.js';

describe('Simulator module structure', () => {
  it('exports generateTagValue from generator', () => {
    expect(typeof generateTagValue).toBe('function');
  });

  it('exports createPublisher from publisher', () => {
    expect(typeof createPublisher).toBe('function');
  });

  it('generateTagValue returns a number within reasonable range', () => {
    const value = generateTagValue(0, 100, 0.5);
    expect(typeof value).toBe('number');
    expect(value).toBeGreaterThanOrEqual(-50);
    expect(value).toBeLessThanOrEqual(150);
  });
});
