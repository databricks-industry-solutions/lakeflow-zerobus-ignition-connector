/**
 * Zerobus publisher - publishes SDT-compressed tag events to Zerobus Ingest.
 *
 * Each raw TagEvent passes through the SDT engine. Only events that survive
 * compression are sent to Zerobus, reducing network and ingest load.
 *
 * Records match the raw_tags schema:
 * event_timestamp, ingest_timestamp, asset_id, asset_type, tag_name,
 * tag_value, quality, source_system, sdt_compressed, compression_ratio
 */

import { SwingingDoorCompressor } from './sdt/swinging-door.js';
import type { TagEvent } from './generator.js';

export interface PublisherConfig {
  endpoint: string;
  clientId: string;
  clientSecret: string;
  table: string;
}

export interface ZerobusClient {
  send: (records: Record<string, unknown>[]) => Promise<void>;
}

export interface ZerobusPublisherConfig {
  client: ZerobusClient;
  sdtCompDev: number;
  sdtCompMax: number;
  sdtCompMin: number;
  streams?: number;
}

export function createPublisher(_config: PublisherConfig) {
  return {
    publish: async () => {
      // Stub for backward compatibility with Phase 1 placeholder test
    },
  };
}

/**
 * Infer asset type from asset ID naming convention.
 * Convention: wind_<site>_t<N> for turbines, bess_<site>_u<N> for battery.
 */
function inferAssetType(assetId: string): string {
  if (assetId.startsWith('wind_')) return 'wind_turbine';
  if (assetId.startsWith('bess_')) return 'battery_bess';
  return 'unknown';
}

export class ZerobusPublisher {
  private client: ZerobusClient;
  private compressors = new Map<string, SwingingDoorCompressor>();
  private sdtCompDev: number;
  private sdtCompMax: number;
  private sdtCompMin: number;
  private pendingRecords: Record<string, unknown>[] = [];

  // Throughput counters (reset each log interval)
  private rawCount = 0;
  private compressedCount = 0;

  constructor(config: ZerobusPublisherConfig) {
    this.client = config.client;
    this.sdtCompDev = config.sdtCompDev;
    this.sdtCompMax = config.sdtCompMax;
    this.sdtCompMin = config.sdtCompMin;
  }

  /** Get or create an SDT compressor for a specific tag key (asset + tag) */
  private getCompressor(key: string): SwingingDoorCompressor {
    let compressor = this.compressors.get(key);
    if (!compressor) {
      compressor = new SwingingDoorCompressor(
        this.sdtCompDev,
        this.sdtCompMax,
        this.sdtCompMin,
      );
      this.compressors.set(key, compressor);
    }
    return compressor;
  }

  /**
   * Process a tag event through SDT and queue for publishing if it survives.
   */
  publish(event: TagEvent): boolean {
    this.rawCount++;

    const key = `${event.assetId}:${event.tagName}`;
    const compressor = this.getCompressor(key);
    const result = compressor.process(
      event.eventTimestamp.getTime(),
      event.tagValue,
    );

    if (result.archive) {
      this.compressedCount++;
      const stats = compressor.getStats();

      const record: Record<string, unknown> = {
        event_timestamp: event.eventTimestamp.toISOString(),
        ingest_timestamp: new Date().toISOString(),
        asset_id: event.assetId,
        asset_type: inferAssetType(event.assetId),
        tag_name: event.tagName,
        tag_value: event.tagValue,
        quality: event.quality,
        source_system: 'ignition_sim',
        sdt_compressed: true,
        compression_ratio: stats.compressionRatio,
      };

      this.pendingRecords.push(record);
      return true;
    }

    return false;
  }

  /** Flush pending records to Zerobus */
  async flush(): Promise<void> {
    if (this.pendingRecords.length === 0) return;
    const batch = this.pendingRecords.splice(0);
    await this.client.send(batch);
  }

  /** Log throughput stats to stdout */
  logThroughput(): void {
    const ratio =
      this.compressedCount > 0
        ? (this.rawCount / this.compressedCount).toFixed(1)
        : 'N/A';
    console.log(
      `[throughput] raw=${this.rawCount} compressed=${this.compressedCount} ratio=${ratio}:1`,
    );
  }

  /** Reset throughput counters (called after each log interval) */
  resetCounters(): void {
    this.rawCount = 0;
    this.compressedCount = 0;
  }

  /** Get current throughput stats */
  getStats(): { rawCount: number; compressedCount: number } {
    return { rawCount: this.rawCount, compressedCount: this.compressedCount };
  }
}
