import { describe, it, expect } from 'vitest';
import { extrapolateScale } from '../extrapolation.js';

describe('Scale extrapolation', () => {
  it('extrapolation formula is correct', () => {
    // 20 assets x 13 tags = 260 tags at 1s interval
    // SDT ratio 6:1 means only 1/6 of raw events are stored
    // Raw rate for 2M tags at 1s = 2,000,000 events/sec
    const result = extrapolateScale({
      actualAssets: 20,
      actualTagsPerAsset: 13,
      frequencyMs: 1000,
      sdtRatio: 6,
      targetTotalTags: 2_000_000,
    });

    // Actual demo metrics
    const expectedActualTags = 20 * 13; // 260
    const expectedActualRawRate = expectedActualTags / 1; // 260 events/sec
    expect(result.actual.totalTags).toBe(expectedActualTags);
    expect(result.actual.rawEventsPerSec).toBe(expectedActualRawRate);
    expect(result.actual.compressedEventsPerSec).toBeCloseTo(
      expectedActualRawRate / 6,
      1,
    );

    // Projected @ 2M tags
    const expectedProjectedRawRate = 2_000_000 / 1; // 2M events/sec
    expect(result.projected.totalTags).toBe(2_000_000);
    expect(result.projected.rawEventsPerSec).toBe(expectedProjectedRawRate);
    expect(result.projected.compressedEventsPerSec).toBeCloseTo(
      expectedProjectedRawRate / 6,
      1,
    );
  });

  it('extrapolation includes compression', () => {
    const result = extrapolateScale({
      actualAssets: 10,
      actualTagsPerAsset: 10,
      frequencyMs: 1000,
      sdtRatio: 4,
      targetTotalTags: 1_000_000,
    });

    // Post-SDT rate should be raw_rate / sdt_ratio
    expect(result.projected.compressedEventsPerSec).toBe(
      result.projected.rawEventsPerSec / 4,
    );
    expect(result.actual.compressedEventsPerSec).toBe(
      result.actual.rawEventsPerSec / 4,
    );

    // Streams needed based on Zerobus 15K rows/sec per stream
    expect(result.projected.streamsNeeded).toBeGreaterThan(0);
  });
});
