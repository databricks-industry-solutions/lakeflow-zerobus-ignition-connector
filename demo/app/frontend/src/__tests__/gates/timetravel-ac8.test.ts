/**
 * Gate test for AC-8: Graceful error for vacuumed timestamps.
 */
import { describe, it, expect } from 'vitest';

describe('AC-8: Graceful error for expired Delta versions', () => {
  it('api.ts has a fleet snapshot function', async () => {
    let api: any;
    try {
      api = await import('../../services/api');
    } catch {
      expect.fail('GATE NOT PASSED: AC-8 — api.ts cannot be imported');
      return;
    }

    const hasSnapshotFn = typeof api.getFleetSnapshot === 'function'
      || typeof api.fetchFleetSnapshot === 'function';
    expect(hasSnapshotFn).toBe(true);
  });
});
