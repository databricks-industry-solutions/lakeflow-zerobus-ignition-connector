import { useCallback } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import BigNumberCard from '../components/BigNumberCard';
import ScalingCalculator from '../components/ScalingCalculator';
import TunablesTable from '../components/TunablesTable';
import { formatNumber, formatLatency, latencyColor } from '../utils/format';

export default function Performance() {
  const throughputFetcher = useCallback(
    () => api.getThroughput().then((r) => r.data),
    [],
  );
  const latencyFetcher = useCallback(
    () => api.getLatency().then((r) => r.data),
    [],
  );

  const throughput = usePolling({
    fetcher: throughputFetcher,
    intervalMs: 5000,
  });
  const latency = usePolling({
    fetcher: latencyFetcher,
    intervalMs: 5000,
  });

  const latest = throughput.data?.at(-1);
  const latestLatency = latency.data?.at(-1);

  return (
    <div>
      <h2 className="font-heading text-2xl font-semibold text-gray-900 mb-4">Performance</h2>

      {/* Live performance cards with progress bars against specs */}
      <h3 className="font-heading text-lg font-medium text-gray-700 mb-3">
        Live performance
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <BigNumberCard
          label="Throughput"
          value={
            latest
              ? `${formatNumber((Number(latest.records_after_sdt) || 0) / 5, 0)}/sec`
              : '-'
          }
          subtitle="of 15K/stream capacity"
          colorClass={latest ? 'text-brand-green' : 'text-databricks-primary'}
          progress={
            latest
              ? { value: (Number(latest.records_after_sdt) || 0) / 5, max: 15000 }
              : undefined
          }
        />
        <BigNumberCard
          label="SDT compression"
          value={
            latest
              ? latest.sdt_enabled === true
                ? Number(latest.sdt_compression_ratio) > 1
                  ? `${formatNumber(Number(latest.sdt_compression_ratio), 1)}:1`
                  : 'On (ratio pending)'
                : 'Off'
              : '-'
          }
          subtitle={
            latest?.sdt_enabled
              ? 'Target: 4-10:1'
              : 'Enable SDT on the gateway connector'
          }
          colorClass={
            latest?.sdt_enabled &&
            Number(latest.sdt_compression_ratio) >= 4 &&
            Number(latest.sdt_compression_ratio) <= 10
              ? 'text-brand-green'
              : latest?.sdt_enabled
                ? 'text-brand-amber'
                : 'text-databricks-primary'
          }
        />
        <BigNumberCard
          label="Avg latency"
          value={latestLatency ? formatLatency(latestLatency.avg_latency_ms) : '-'}
          subtitle="of 5s target"
          colorClass={
            latestLatency
              ? latencyColor(latestLatency.avg_latency_ms)
              : 'text-databricks-primary'
          }
          progress={
            latestLatency
              ? { value: Number(latestLatency.avg_latency_ms), max: 5000 }
              : undefined
          }
        />
        <BigNumberCard
          label="P99 latency"
          value={latestLatency ? formatLatency(latestLatency.p99_latency_ms) : '-'}
          subtitle="of 5s target"
          colorClass={
            latestLatency
              ? latencyColor(latestLatency.p99_latency_ms)
              : 'text-databricks-primary'
          }
          progress={
            latestLatency
              ? { value: Number(latestLatency.p99_latency_ms), max: 5000 }
              : undefined
          }
        />
      </div>

      {/* Section 3 - Scaling calculator */}
      <h3 className="text-lg font-medium text-gray-700 mb-3">
        Scaling calculator
      </h3>
      <div className="mb-6">
        <ScalingCalculator />
      </div>

      {/* Section 4 - Connector tunables */}
      <h3 className="text-lg font-medium text-gray-700 mb-3">
        Connector configuration
      </h3>
      <TunablesTable />
    </div>
  );
}
