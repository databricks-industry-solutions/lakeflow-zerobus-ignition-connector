import { useCallback, useEffect, useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import type { SdtConfigEntry } from '../services/api';
import CompressionWaterfall from '../components/CompressionWaterfall';
import type { CompressionLayer } from '../components/CompressionWaterfall';
import SdtTuningPanel from '../components/SdtTuningPanel';

/** Default SDT tuning values when config is not yet loaded or table is missing. */
const DEFAULT_COMP_DEV_PERCENT = 1.0;
const DEFAULT_COMP_MAX_SECONDS = 600;

export default function Compression() {
  const comparisonFetcher = useCallback(
    () =>
      api.getCompressionComparison().then((r) => {
        const data = r?.data;
        return Array.isArray(data) ? data : [];
      }) as Promise<CompressionLayer[]>,
    [],
  );

  const comparison = usePolling({
    fetcher: comparisonFetcher,
    intervalMs: 10000,
  });

  const [sdtConfig, setSdtConfig] = useState<SdtConfigEntry[] | null>(null);
  const [sdtConfigError, setSdtConfigError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSdtConfig()
      .then((r) => {
        const data = r?.data;
        setSdtConfig(Array.isArray(data) ? data : []);
        setSdtConfigError(null);
      })
      .catch((err) => {
        setSdtConfig(null);
        setSdtConfigError(
          err?.message ?? 'SDT config unavailable. Ensure sdt_config table exists and the app has MODIFY, SELECT.',
        );
      });
  }, []);

  const handleApply = useCallback(
    async (config: { comp_dev_percent: number; comp_max_seconds: number }) => {
      await api.updateSdtConfig({ tag_pattern: '*', ...config });
      const r = await api.getSdtConfig();
      const data = r?.data;
      setSdtConfig(Array.isArray(data) ? data : []);
      setSdtConfigError(null);
    },
    [],
  );

  const layers = Array.isArray(comparison.data) ? comparison.data : [];
  const rawLayer = layers.find((l) => l.layer_name === 'raw');
  const deltaLayer =
    layers.find((l) => l.layer_name === 'after_delta') ?? layers.find((l) => l.layer_name === 'combined');
  const formatBytes = (b: number) => {
    const n = Number(b);
    if (n === 0 || !Number.isFinite(n)) return '0 B';
    if (n >= 1e9) return `${(n / 1e9).toFixed(2)} GB`;
    if (n >= 1e6) return `${(n / 1e6).toFixed(2)} MB`;
    if (n >= 1e3) return `${(n / 1e3).toFixed(2)} KB`;
    return `${Math.round(n)} B`;
  };

  const defaultRow =
    sdtConfig?.find((r) => r.tag_pattern === '*') ?? sdtConfig?.[0];
  const compDevPercent =
    defaultRow?.comp_dev_percent != null ? defaultRow.comp_dev_percent : DEFAULT_COMP_DEV_PERCENT;
  const compMaxSeconds =
    defaultRow?.comp_max_seconds != null ? defaultRow.comp_max_seconds : DEFAULT_COMP_MAX_SECONDS;

  return (
    <div>
      <h2 className="font-heading text-2xl font-semibold text-gray-900 mb-4">Compression</h2>

      {/* Data volume summary */}
      {rawLayer != null && deltaLayer != null && (
        <p className="text-sm text-gray-600 mb-4">
          Last 30 min: {rawLayer.event_count.toLocaleString()} rows ingested → {formatBytes(rawLayer.size_bytes)}{' '}
          (est.) → {formatBytes(deltaLayer.size_bytes)} on disk (Delta Lake, ZSTD).
        </p>
      )}

      {/* Waterfall section */}
      <div className="mb-6">
        <CompressionWaterfall layers={layers} />
      </div>

      {/* SDT tuning panel */}
      <div>
        {sdtConfigError && (
          <p className="text-sm text-amber-500 mb-2" role="alert">
            {sdtConfigError}
          </p>
        )}
        <SdtTuningPanel
          compDevPercent={compDevPercent}
          compMaxSeconds={compMaxSeconds}
          onApply={handleApply}
        />
      </div>
    </div>
  );
}
