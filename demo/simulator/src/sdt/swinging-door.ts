/**
 * Swinging Door Trending (SDT) compression engine.
 *
 * Implements the published Swinging Door algorithm (common historian semantics):
 *
 * 1. When a new value arrives, compute slopes from the last archived point
 *    to the new value +/- CompDev.
 * 2. Maintain running slope_max and slope_min (the "swinging doors").
 * 3. If slope_min > slope_max, the doors have crossed - archive the *previous*
 *    value and reset the algorithm from that new archived point.
 * 4. If CompMax seconds elapse since last archive, force-archive current value.
 * 5. If less than CompMin seconds since last archive, skip (don't archive).
 *
 * Timestamps are in milliseconds for JS compatibility.
 */

export interface ArchivedValue {
  timestamp: number;
  value: number;
}

export interface ProcessResult {
  archive: boolean;
  archivedValue?: ArchivedValue;
}

export interface CompressorStats {
  rawCount: number;
  archivedCount: number;
  compressionRatio: number;
}

export class SwingingDoorCompressor {
  private compDev: number;
  private compMaxMs: number;
  private compMinMs: number;

  // Last archived point
  private lastArchived: ArchivedValue | null = null;
  // Previous point (candidate for archiving when doors cross)
  private prevPoint: ArchivedValue | null = null;
  // Running slope bounds (the "doors")
  private slopeMax: number = -Infinity;
  private slopeMin: number = Infinity;

  // Stats
  private rawCount = 0;
  private archivedCount = 0;

  /**
   * @param compDev - Compression deviation in engineering units
   * @param compMaxSeconds - Max seconds between archived values (force archive)
   * @param compMinSeconds - Min seconds between archived values (suppress rapid changes)
   */
  constructor(compDev: number, compMaxSeconds: number, compMinSeconds: number) {
    this.compDev = compDev;
    this.compMaxMs = compMaxSeconds * 1000;
    this.compMinMs = compMinSeconds * 1000;
  }

  /**
   * Process a new value through the SDT filter.
   * @param timestamp - Timestamp in milliseconds
   * @param value - Numeric tag value
   * @returns Whether to archive and the archived value if applicable
   */
  process(timestamp: number, value: number): ProcessResult {
    this.rawCount++;

    // First value is always archived
    if (this.lastArchived === null) {
      this.lastArchived = { timestamp, value };
      this.prevPoint = null;
      this.slopeMax = -Infinity;
      this.slopeMin = Infinity;
      this.archivedCount++;
      return { archive: true, archivedValue: { timestamp, value } };
    }

    const dt = timestamp - this.lastArchived.timestamp;

    // CompMin check: suppress if too soon since last archive
    if (dt < this.compMinMs && this.compMinMs > 0) {
      this.prevPoint = { timestamp, value };
      return { archive: false };
    }

    // CompMax check: force archive if too long since last archive
    if (dt >= this.compMaxMs && this.compMaxMs > 0) {
      this.lastArchived = { timestamp, value };
      this.prevPoint = null;
      this.slopeMax = -Infinity;
      this.slopeMin = Infinity;
      this.archivedCount++;
      return { archive: true, archivedValue: { timestamp, value } };
    }

    // Compute slopes from last archived point to new value +/- CompDev
    // slope_upper = (value + compDev - lastArchived.value) / dt
    // slope_lower = (value - compDev - lastArchived.value) / dt
    const slopeUpper = (value + this.compDev - this.lastArchived.value) / dt;
    const slopeLower = (value - this.compDev - this.lastArchived.value) / dt;

    // Tighten the doors: slopeMax can only decrease, slopeMin can only increase
    const newSlopeMax =
      this.slopeMax === -Infinity
        ? slopeUpper
        : Math.min(this.slopeMax, slopeUpper);
    const newSlopeMin =
      this.slopeMin === Infinity
        ? slopeLower
        : Math.max(this.slopeMin, slopeLower);

    // Check if doors have crossed
    if (newSlopeMin > newSlopeMax) {
      // Archive the previous point (the last point before crossing)
      const archivePoint = this.prevPoint ?? { timestamp, value };
      this.lastArchived = archivePoint;
      this.archivedCount++;

      // Reset doors and re-evaluate current point from the new archive
      this.slopeMax = -Infinity;
      this.slopeMin = Infinity;
      this.prevPoint = { timestamp, value };

      // Re-compute slopes from the newly archived point to current value
      const newDt = timestamp - this.lastArchived.timestamp;
      if (newDt > 0) {
        this.slopeMax =
          (value + this.compDev - this.lastArchived.value) / newDt;
        this.slopeMin =
          (value - this.compDev - this.lastArchived.value) / newDt;
      }

      return { archive: true, archivedValue: archivePoint };
    }

    // Doors haven't crossed - update slopes and continue
    this.slopeMax = newSlopeMax;
    this.slopeMin = newSlopeMin;
    this.prevPoint = { timestamp, value };
    return { archive: false };
  }

  /** Get compression statistics */
  getStats(): CompressorStats {
    return {
      rawCount: this.rawCount,
      archivedCount: this.archivedCount,
      compressionRatio:
        this.archivedCount > 0 ? this.rawCount / this.archivedCount : 0,
    };
  }

  /** Reset the compressor state */
  reset(): void {
    this.lastArchived = null;
    this.prevPoint = null;
    this.slopeMax = -Infinity;
    this.slopeMin = Infinity;
    this.rawCount = 0;
    this.archivedCount = 0;
  }
}
