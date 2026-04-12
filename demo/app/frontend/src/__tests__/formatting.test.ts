import { describe, it, expect } from 'vitest';
import { formatNumber, formatTimestamp } from '../utils/format';

describe('Number formatting', () => {
  it('outputs locale-appropriate commas and 2 decimal places', () => {
    const result = formatNumber(1234567.89, 2);
    // en-AU uses commas as thousands separator
    expect(result).toBe('1,234,567.89');
  });

  it('handles zero decimal places', () => {
    const result = formatNumber(1234567, 0);
    expect(result).toBe('1,234,567');
  });

  it('handles small numbers', () => {
    const result = formatNumber(42.5, 2);
    expect(result).toBe('42.50');
  });
});

describe('Timestamp formatting', () => {
  it('outputs human-readable time format', () => {
    const ts = '2026-02-12T14:30:45.000Z';
    const result = formatTimestamp(ts);
    // Should produce a time string like HH:MM:SS
    expect(result).toMatch(/\d{1,2}:\d{2}:\d{2}/);
  });
});
