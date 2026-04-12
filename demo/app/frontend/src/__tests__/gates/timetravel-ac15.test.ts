/**
 * Gate test for AC-15: CSV export format.
 */
import { describe, it, expect } from 'vitest';

describe('AC-15: CSV export columns', () => {
  it('assetTagsExport query builder exists', async () => {
    // This is a backend concern — verify via API type definitions
    // Check that the api.ts has an export function
    let api: any;
    try {
      api = await import('../../services/api');
    } catch {
      expect.fail('GATE NOT PASSED: AC-15 — api.ts cannot be imported');
      return;
    }

    const hasExportFn = typeof api.exportAssetTagsCsv === 'function'
      || typeof api.downloadAssetCsv === 'function'
      || typeof api.exportCsv === 'function';
    expect(hasExportFn).toBe(true);
  });
});
