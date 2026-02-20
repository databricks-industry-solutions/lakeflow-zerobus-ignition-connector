import { useCallback } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import type { HealthScoreRow, RevenueRiskRow, RevenueSummary } from '../services/api';
import BigNumberCard from '../components/BigNumberCard';
import { formatNumber } from '../utils/format';

const VALUE_PROP =
  'Which assets are at risk, and how much revenue could we lose if they trip during the next high-price NEM window?';

function formatDateTime(ts: string | null | undefined): string {
  if (ts == null) return '-';
  const d = new Date(ts);
  return d.toLocaleString('en-AU', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
}

function healthColor(score: number | null | undefined): string {
  if (score == null) return 'text-gray-600';
  if (score >= 0.8) return 'text-brand-green';
  if (score >= 0.5) return 'text-brand-amber';
  return 'text-brand-red';
}

export default function Analytics() {
  const summaryFetcher = useCallback(
    () => api.getRevenueSummary().then((r) => r.data),
    [],
  );
  const healthFetcher = useCallback(
    () => api.getHealthScores().then((r) => r.data),
    [],
  );
  const riskFetcher = useCallback(
    () => api.getRevenueRisk().then((r) => r.data),
    [],
  );

  const { data: summary } = usePolling<RevenueSummary | undefined>({
    fetcher: summaryFetcher,
    intervalMs: 10000,
  });
  const { data: healthScores } = usePolling<HealthScoreRow[] | undefined>({
    fetcher: healthFetcher,
    intervalMs: 10000,
  });
  const { data: revenueRisk } = usePolling<RevenueRiskRow[] | undefined>({
    fetcher: riskFetcher,
    intervalMs: 10000,
  });

  const assetsAtRisk = summary?.assets_at_risk ?? 0;
  const totalAtRisk = summary?.total_revenue_at_risk_aud ?? 0;
  const avgHealth = summary?.avg_health_score ?? null;
  const nextWindow = summary?.next_risk_window ?? null;

  const avgHealthAccent =
    avgHealth != null
      ? avgHealth >= 0.8
        ? ('success' as const)
        : avgHealth >= 0.5
          ? ('warning' as const)
          : ('error' as const)
      : undefined;

  return (
    <div>
      <h2 className="font-heading text-2xl font-semibold text-gray-900 mb-2">Fleet health & revenue risk</h2>
      <p className="text-gray-600 mb-6 max-w-2xl">
        This pipeline answers: <strong className="text-gray-800">{VALUE_PROP}</strong>
      </p>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <BigNumberCard
          label="Total revenue at risk"
          value={totalAtRisk > 0 ? `$${formatNumber(totalAtRisk, 0)}` : '$0'}
          subtitle="AUD (upcoming high-price windows)"
          colorClass={totalAtRisk > 0 ? 'text-brand-amber' : 'text-brand-green'}
          accent={totalAtRisk > 0 ? 'warning' : 'success'}
        />
        <BigNumberCard
          label="Assets at risk"
          value={assetsAtRisk}
          subtitle="With revenue at risk > 0"
        />
        <BigNumberCard
          label="Avg fleet health"
          value={avgHealth != null ? formatNumber(avgHealth, 2) : '-'}
          subtitle="0 = critical, 1 = healthy"
          colorClass={healthColor(avgHealth)}
          accent={avgHealthAccent}
        />
        <BigNumberCard
          label="Next risk window"
          value={nextWindow ? formatDateTime(nextWindow) : '-'}
          subtitle="Start of next high-price window"
        />
      </div>

      {/* Health by asset */}
      <section className="mb-8">
        <h3 className="font-heading text-lg font-semibold text-gray-700 mb-3">Health by asset</h3>
        <div className="overflow-x-auto border border-gray-200 rounded-card bg-surface-card shadow-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-gray-700 border-b-2 border-gray-200">
                <th className="px-4 py-3 font-semibold">Asset</th>
                <th className="px-4 py-3 font-semibold">Health</th>
                <th className="px-4 py-3 font-semibold">Primary risk tag</th>
                <th className="px-4 py-3 font-semibold">Risk description</th>
              </tr>
            </thead>
            <tbody>
              {(healthScores ?? []).length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-gray-500">
                    No health scores yet. Run the pipeline and ensure enriched_tags and
                    silver_asset_registry are populated.
                  </td>
                </tr>
              ) : (
                (healthScores ?? []).map((row) => (
                  <tr key={row.asset_id} className="border-t border-gray-200 hover:bg-gray-100/50">
                    <td className="px-4 py-3 font-mono text-gray-700">{row.asset_id}</td>
                    <td className={`px-4 py-3 font-semibold ${healthColor(row.health_score)}`}>
                      {formatNumber(row.health_score, 2)}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{row.primary_risk_tag ?? '-'}</td>
                    <td className="px-4 py-3 text-gray-600 max-w-md truncate">
                      {row.risk_description ?? '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Revenue at risk by asset */}
      <section>
        <h3 className="font-heading text-lg font-semibold text-gray-700 mb-3">Revenue at risk by asset</h3>
        <div className="overflow-x-auto border border-gray-200 rounded-card bg-surface-card shadow-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-gray-700 border-b-2 border-gray-200">
                <th className="px-4 py-3 font-semibold">Asset</th>
                <th className="px-4 py-3 font-semibold">Risk window</th>
                <th className="px-4 py-3 font-semibold">Forecast $/MWh</th>
                <th className="px-4 py-3 font-semibold">Capacity MW</th>
                <th className="px-4 py-3 font-semibold">Health</th>
                <th className="px-4 py-3 font-semibold">Trip prob.</th>
                <th className="px-4 py-3 font-semibold">Revenue at risk (AUD)</th>
                <th className="px-4 py-3 font-semibold">Recommended action</th>
              </tr>
            </thead>
            <tbody>
              {(revenueRisk ?? []).length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-6 text-center text-gray-500">
                    No revenue risk rows yet. Run the pipeline; revenue_risk is computed from
                    health_scores and price_forecast (high-price windows).
                  </td>
                </tr>
              ) : (
                (revenueRisk ?? []).map((row, i) => (
                  <tr
                    key={`${row.asset_id}-${row.risk_window_start}-${i}`}
                    className="border-t border-gray-200 hover:bg-gray-100/50"
                  >
                    <td className="px-4 py-3 font-mono text-gray-700">{row.asset_id}</td>
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                      {formatDateTime(row.risk_window_start)} → {formatDateTime(row.risk_window_end)}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {formatNumber(row.forecast_price_aud_mwh, 0)}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {formatNumber(row.asset_capacity_mw, 0)}
                    </td>
                    <td className={`px-4 py-3 font-semibold ${healthColor(row.health_score)}`}>
                      {row.health_score != null ? formatNumber(row.health_score, 2) : '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {formatNumber(row.trip_probability, 2)}
                    </td>
                    <td className="px-4 py-3 font-semibold text-brand-amber">
                      ${formatNumber(row.revenue_at_risk_aud, 0)}
                    </td>
                    <td className="px-4 py-3 text-gray-600 max-w-xs">{row.recommended_action}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
