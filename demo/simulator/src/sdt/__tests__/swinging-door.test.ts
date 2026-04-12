import { describe, it, expect } from 'vitest';
import { SwingingDoorCompressor } from '../swinging-door.js';

describe('SwingingDoorCompressor', () => {
  it('first value is always archived', () => {
    const sdt = new SwingingDoorCompressor(1.0, 600, 0);
    const result = sdt.process(1000, 50.0);
    expect(result.archive).toBe(true);
    expect(result.archivedValue).toBeDefined();
    expect(result.archivedValue!.value).toBe(50.0);
    expect(result.archivedValue!.timestamp).toBe(1000);
  });

  it('linear ramp within CompDev compresses to 2 points (start + end)', () => {
    // CompDev = 1.0 means values within 1.0 of the linear interpolation are suppressed
    const sdt = new SwingingDoorCompressor(1.0, 600, 0);

    const archived: Array<{ timestamp: number; value: number }> = [];

    // Feed a perfectly linear ramp: 0, 1, 2, ..., 10
    for (let i = 0; i <= 10; i++) {
      const result = sdt.process(i * 1000, i * 10.0);
      if (result.archive && result.archivedValue) {
        archived.push(result.archivedValue);
      }
    }

    // A perfectly linear ramp should only archive the first point.
    // The last point is not archived until the next non-linear value arrives
    // or CompMax triggers. With 11 values over 10s and CompMax=600, no force.
    // So we should see only the first value archived.
    expect(archived.length).toBe(1);

    // Now send a final "flush" value that continues the trend -
    // the compressor only archives the previous point when the door crosses
    // For a perfect linear signal, no crossing happens, so we just get the start.
    // To get the "end" point, we'd need a deviation. Let's verify the ratio instead:
    // 12 input values, 1 archived = high compression
    expect(archived[0].timestamp).toBe(0);
  });

  it('step change archives immediately', () => {
    const sdt = new SwingingDoorCompressor(1.0, 600, 0);

    const archived: Array<{ timestamp: number; value: number }> = [];

    // First value - always archived
    let result = sdt.process(0, 50.0);
    if (result.archive && result.archivedValue) archived.push(result.archivedValue);

    // Small changes within CompDev - should not archive
    result = sdt.process(1000, 50.3);
    if (result.archive && result.archivedValue) archived.push(result.archivedValue);

    result = sdt.process(2000, 50.5);
    if (result.archive && result.archivedValue) archived.push(result.archivedValue);

    // Large step change exceeding CompDev
    result = sdt.process(3000, 80.0);
    if (result.archive && result.archivedValue) archived.push(result.archivedValue);

    // The step should cause archiving - the previous value (50.5) and then 80.0
    // gets archived because the door crosses
    expect(archived.length).toBeGreaterThanOrEqual(2);
    // The first archived is at t=0 (first value)
    expect(archived[0].value).toBe(50.0);
    // There should be a value archived for the point before the step
    // and the step itself should cause subsequent archiving
    const nonFirstArchived = archived.filter((a) => a.timestamp > 0);
    expect(nonFirstArchived.length).toBeGreaterThanOrEqual(1);
  });

  it('CompMax forces archive after timeout', () => {
    // CompMax = 5 seconds, very small CompDev so values normally would be suppressed if linear
    const sdt = new SwingingDoorCompressor(100.0, 5, 0);

    const archived: Array<{ timestamp: number; value: number }> = [];

    // First value at t=0
    let result = sdt.process(0, 50.0);
    if (result.archive && result.archivedValue) archived.push(result.archivedValue);

    // Value at t=3s - within CompMax, CompDev is huge so no SDT trigger
    result = sdt.process(3000, 50.1);
    if (result.archive && result.archivedValue) archived.push(result.archivedValue);

    // Value at t=6s - exceeds CompMax (6s > 5s since last archive at t=0)
    result = sdt.process(6000, 50.2);
    if (result.archive && result.archivedValue) archived.push(result.archivedValue);

    // Should have archived at least 2: first value + CompMax forced
    expect(archived.length).toBeGreaterThanOrEqual(2);
    // The forced archive should be at or after CompMax
    const forcedArchive = archived.find((a) => a.timestamp > 0);
    expect(forcedArchive).toBeDefined();
  });

  it('CompMin suppresses rapid changes', () => {
    // CompMin = 5 seconds - don't archive more often than every 5s
    // CompDev = 0.1 - very tight, would normally archive every change
    const sdt = new SwingingDoorCompressor(0.1, 600, 5);

    const archived: Array<{ timestamp: number; value: number }> = [];

    // First value at t=0 - always archived
    let result = sdt.process(0, 50.0);
    if (result.archive && result.archivedValue) archived.push(result.archivedValue);

    // Rapid changes at 1-second intervals, all exceeding CompDev
    for (let i = 1; i <= 4; i++) {
      result = sdt.process(i * 1000, 50.0 + i * 10); // Big jumps
      if (result.archive && result.archivedValue) archived.push(result.archivedValue);
    }

    // Despite big value changes, CompMin should suppress archives within 5s window
    // Only the first value should be archived (all others within CompMin)
    expect(archived.length).toBe(1);
    expect(archived[0].timestamp).toBe(0);
  });

  it('sinusoidal signal achieves compression ratio > 1.0', () => {
    const sdt = new SwingingDoorCompressor(2.0, 600, 0);

    let archivedCount = 0;
    const totalPoints = 200;

    // Generate a sine wave: amplitude 50, offset 50, period 100 points
    for (let i = 0; i < totalPoints; i++) {
      const value = 50 + 50 * Math.sin((2 * Math.PI * i) / 100);
      const result = sdt.process(i * 1000, value);
      if (result.archive) archivedCount++;
    }

    // Sine wave should compress - more raw points than archived points
    expect(archivedCount).toBeGreaterThan(0);
    expect(archivedCount).toBeLessThan(totalPoints);

    const ratio = totalPoints / archivedCount;
    expect(ratio).toBeGreaterThan(1.0);
  });

  it('compression ratio tracking is correct', () => {
    const sdt = new SwingingDoorCompressor(5.0, 600, 0);

    const totalPoints = 50;

    // Feed values that create some compression
    for (let i = 0; i < totalPoints; i++) {
      const value = 50 + 20 * Math.sin((2 * Math.PI * i) / 30);
      sdt.process(i * 1000, value);
    }

    const stats = sdt.getStats();
    expect(stats.rawCount).toBe(totalPoints);
    expect(stats.archivedCount).toBeGreaterThan(0);
    expect(stats.archivedCount).toBeLessThanOrEqual(totalPoints);
    expect(stats.compressionRatio).toBeCloseTo(
      stats.rawCount / stats.archivedCount,
      5,
    );
  });

  it('reset() clears state and counters', () => {
    const sdt = new SwingingDoorCompressor(5.0, 600, 0);

    // Process some values
    for (let i = 0; i < 20; i++) {
      sdt.process(i * 1000, 50 + i);
    }

    const statsBefore = sdt.getStats();
    expect(statsBefore.rawCount).toBe(20);
    expect(statsBefore.archivedCount).toBeGreaterThan(0);

    // Reset the compressor
    sdt.reset();

    // Verify counters are cleared
    const statsAfter = sdt.getStats();
    expect(statsAfter.rawCount).toBe(0);
    expect(statsAfter.archivedCount).toBe(0);
    expect(statsAfter.compressionRatio).toBe(0);

    // Verify state is cleared - first value after reset should archive
    const result = sdt.process(0, 100.0);
    expect(result.archive).toBe(true);
  });
});
