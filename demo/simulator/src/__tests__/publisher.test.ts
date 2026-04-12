import { describe, it, expect, vi } from 'vitest';
import { ZerobusPublisher, createPublisher } from '../publisher.js';
import type { TagEvent } from '../generator.js';

describe('ZerobusPublisher', () => {
  it('produces records matching raw_tags schema', async () => {
    const sentRecords: Record<string, unknown>[] = [];
    const mockClient = {
      send: async (records: Record<string, unknown>[]) => {
        sentRecords.push(...records);
      },
    };

    const publisher = new ZerobusPublisher({
      client: mockClient,
      sdtCompDev: 100, // Large CompDev so event passes through
      sdtCompMax: 600,
      sdtCompMin: 0,
    });

    const event: TagEvent = {
      eventTimestamp: new Date('2025-01-15T10:00:00Z'),
      assetId: 'wind_hexham_t01',
      tagName: 'generator/power_kw',
      tagValue: 2500.0,
      quality: 192,
    };

    publisher.publish(event);
    await publisher.flush();

    expect(sentRecords.length).toBe(1);
    const record = sentRecords[0];

    // Verify all required columns from raw_tags schema
    expect(record).toHaveProperty('event_timestamp');
    expect(record).toHaveProperty('ingest_timestamp');
    expect(record).toHaveProperty('asset_id', 'wind_hexham_t01');
    expect(record).toHaveProperty('asset_type');
    expect(record).toHaveProperty('tag_name', 'generator/power_kw');
    expect(record).toHaveProperty('tag_value', 2500.0);
    expect(record).toHaveProperty('quality', 192);
    expect(record).toHaveProperty('source_system', 'ignition_sim');
    expect(record).toHaveProperty('sdt_compressed', true);
    expect(record).toHaveProperty('compression_ratio');
  });

  it('only sends SDT-surviving events', async () => {
    const sentRecords: Record<string, unknown>[] = [];
    const mockClient = {
      send: async (records: Record<string, unknown>[]) => {
        sentRecords.push(...records);
      },
    };

    // Tight CompDev = 0.1, but values will be very close (within CompDev)
    const publisher = new ZerobusPublisher({
      client: mockClient,
      sdtCompDev: 0.5,
      sdtCompMax: 600,
      sdtCompMin: 0,
    });

    const baseTime = new Date('2025-01-15T10:00:00Z').getTime();

    // Feed 100 events with small linear drift (within CompDev)
    for (let i = 0; i < 100; i++) {
      const event: TagEvent = {
        eventTimestamp: new Date(baseTime + i * 1000),
        assetId: 'wind_hexham_t01',
        tagName: 'generator/power_kw',
        tagValue: 50.0 + i * 0.001, // Very small changes - mostly compressed away
        quality: 192,
      };
      publisher.publish(event);
    }
    await publisher.flush();

    // SDT should compress the near-constant signal heavily
    expect(sentRecords.length).toBeLessThan(100);
    expect(sentRecords.length).toBeGreaterThan(0);
  });

  it('logs throughput', () => {
    const mockClient = {
      send: async () => {},
    };

    const publisher = new ZerobusPublisher({
      client: mockClient,
      sdtCompDev: 1.0,
      sdtCompMax: 600,
      sdtCompMin: 0,
    });

    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

    const baseTime = new Date('2025-01-15T10:00:00Z').getTime();
    for (let i = 0; i < 10; i++) {
      publisher.publish({
        eventTimestamp: new Date(baseTime + i * 1000),
        assetId: 'wind_hexham_t01',
        tagName: 'test/tag',
        tagValue: i * 10,
        quality: 192,
      });
    }

    publisher.logThroughput();

    // Verify that throughput log was called with expected content
    expect(logSpy).toHaveBeenCalled();
    const logCall = logSpy.mock.calls[0][0] as string;
    expect(logCall).toContain('raw');
    expect(logCall).toContain('compressed');
    expect(logCall).toContain('ratio');

    logSpy.mockRestore();
  });

  it('infers battery_bess asset type from bess_ prefix', async () => {
    const sentRecords: Record<string, unknown>[] = [];
    const mockClient = {
      send: async (records: Record<string, unknown>[]) => {
        sentRecords.push(...records);
      },
    };

    const publisher = new ZerobusPublisher({
      client: mockClient,
      sdtCompDev: 100,
      sdtCompMax: 600,
      sdtCompMin: 0,
    });

    const event: TagEvent = {
      eventTimestamp: new Date('2025-01-15T10:00:00Z'),
      assetId: 'bess_liddell_u01',
      tagName: 'battery/soc_pct',
      tagValue: 85.0,
      quality: 192,
    };

    publisher.publish(event);
    await publisher.flush();

    expect(sentRecords.length).toBe(1);
    expect(sentRecords[0]).toHaveProperty('asset_type', 'battery_bess');
  });

  it('infers unknown asset type for other prefixes', async () => {
    const sentRecords: Record<string, unknown>[] = [];
    const mockClient = {
      send: async (records: Record<string, unknown>[]) => {
        sentRecords.push(...records);
      },
    };

    const publisher = new ZerobusPublisher({
      client: mockClient,
      sdtCompDev: 100,
      sdtCompMax: 600,
      sdtCompMin: 0,
    });

    const event: TagEvent = {
      eventTimestamp: new Date('2025-01-15T10:00:00Z'),
      assetId: 'solar_panel_01',
      tagName: 'power_kw',
      tagValue: 100.0,
      quality: 192,
    };

    publisher.publish(event);
    await publisher.flush();

    expect(sentRecords.length).toBe(1);
    expect(sentRecords[0]).toHaveProperty('asset_type', 'unknown');
  });

  it('getStats returns current counters', () => {
    const mockClient = { send: async () => {} };
    const publisher = new ZerobusPublisher({
      client: mockClient,
      sdtCompDev: 100,
      sdtCompMax: 600,
      sdtCompMin: 0,
    });

    // Initial stats should be zero
    expect(publisher.getStats()).toEqual({ rawCount: 0, compressedCount: 0 });

    // Publish some events
    publisher.publish({
      eventTimestamp: new Date(),
      assetId: 'wind_test_t01',
      tagName: 'test/tag',
      tagValue: 50.0,
      quality: 192,
    });

    const stats = publisher.getStats();
    expect(stats.rawCount).toBe(1);
    expect(stats.compressedCount).toBeGreaterThanOrEqual(0);
  });

  it('resetCounters clears throughput counts', () => {
    const mockClient = { send: async () => {} };
    const publisher = new ZerobusPublisher({
      client: mockClient,
      sdtCompDev: 100,
      sdtCompMax: 600,
      sdtCompMin: 0,
    });

    // Publish some events
    for (let i = 0; i < 5; i++) {
      publisher.publish({
        eventTimestamp: new Date(Date.now() + i * 1000),
        assetId: 'wind_test_t01',
        tagName: 'test/tag',
        tagValue: i * 10,
        quality: 192,
      });
    }

    expect(publisher.getStats().rawCount).toBe(5);

    publisher.resetCounters();

    expect(publisher.getStats()).toEqual({ rawCount: 0, compressedCount: 0 });
  });

  it('logThroughput shows N/A ratio when no compressed events', () => {
    const mockClient = { send: async () => {} };
    const publisher = new ZerobusPublisher({
      client: mockClient,
      sdtCompDev: 100,
      sdtCompMax: 600,
      sdtCompMin: 0,
    });

    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

    // Log without publishing anything
    publisher.logThroughput();

    expect(logSpy).toHaveBeenCalled();
    const logCall = logSpy.mock.calls[0][0] as string;
    expect(logCall).toContain('N/A');

    logSpy.mockRestore();
  });
});

describe('createPublisher', () => {
  it('returns a publisher stub with publish method', async () => {
    const publisher = createPublisher({
      endpoint: 'http://example.com',
      clientId: 'test-id',
      clientSecret: 'test-secret',
      table: 'test.table',
    });

    expect(publisher).toHaveProperty('publish');
    expect(typeof publisher.publish).toBe('function');

    // Should not throw
    await publisher.publish();
  });
});
