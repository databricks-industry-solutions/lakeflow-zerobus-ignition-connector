/**
 * Scale extrapolation logic (FR-009).
 *
 * Given the actual demo parameters (assets, tags per asset, frequency, SDT ratio),
 * projects what the metrics would be at production scale (e.g., 2M+ tags).
 *
 * Extrapolation formula:
 *   raw_events_per_sec = total_tags / (frequency_ms / 1000)
 *   compressed_events_per_sec = raw_events_per_sec / sdt_ratio
 *   streams_needed = ceil(compressed_events_per_sec / ZEROBUS_ROWS_PER_SEC_PER_STREAM)
 *
 * Zerobus capacity: 15,000 rows/sec per stream (Public Preview limit).
 */

const ZEROBUS_ROWS_PER_SEC_PER_STREAM = 15_000;

export interface ExtrapolationInput {
  actualAssets: number;
  actualTagsPerAsset: number;
  frequencyMs: number;
  sdtRatio: number;
  targetTotalTags: number;
}

export interface ScaleMetrics {
  totalTags: number;
  rawEventsPerSec: number;
  compressedEventsPerSec: number;
  streamsNeeded: number;
}

export interface ExtrapolationResult {
  actual: ScaleMetrics;
  projected: ScaleMetrics;
}

function computeMetrics(
  totalTags: number,
  frequencyMs: number,
  sdtRatio: number,
): ScaleMetrics {
  const frequencySec = frequencyMs / 1000;
  const rawEventsPerSec = totalTags / frequencySec;
  const compressedEventsPerSec = rawEventsPerSec / sdtRatio;
  const streamsNeeded = Math.ceil(
    compressedEventsPerSec / ZEROBUS_ROWS_PER_SEC_PER_STREAM,
  );
  return { totalTags, rawEventsPerSec, compressedEventsPerSec, streamsNeeded };
}

/**
 * Compute projected scale metrics for actual demo and target production scale.
 */
export function extrapolateScale(input: ExtrapolationInput): ExtrapolationResult {
  const actualTotalTags = input.actualAssets * input.actualTagsPerAsset;

  return {
    actual: computeMetrics(actualTotalTags, input.frequencyMs, input.sdtRatio),
    projected: computeMetrics(
      input.targetTotalTags,
      input.frequencyMs,
      input.sdtRatio,
    ),
  };
}
