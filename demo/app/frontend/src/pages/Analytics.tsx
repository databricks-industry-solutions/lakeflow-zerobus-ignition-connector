import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import type { HealthScoreRow, RevenueRiskRow, RevenueSummary } from '../services/api';
import BigNumberCard from '../components/BigNumberCard';
import { formatNumber } from '../utils/format';

const VALUE_PROP =
  'Which assets are at risk, and how much revenue could we lose if they trip during the next high-price market window?';

function formatDateTime(ts: string | null | undefined): string {
  if (ts == null) return '-';
  const d = new Date(ts);
  return d.toLocaleString('en-US', {
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

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function Analytics() {
  const navigate = useNavigate();

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

  // Fleet Snapshot state
  const [snapshotTimestamp, setSnapshotTimestamp] = useState(
    toLocalInput(new Date(Date.now() - 2 * 60 * 60 * 1000)),
  );
  const [snapshotData, setSnapshotData] = useState<HealthScoreRow[] | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [showCompare, setShowCompare] = useState(false);
  const [showSql, setShowSql] = useState(false);

  const snapshotSql = `SELECT scored_at, asset_id, health_score, primary_risk_tag,
       risk_description, anomaly_tags, estimated_hours_to_failure
FROM catalog.schema.health_score_history
WHERE scored_at <= '${new Date(snapshotTimestamp).toISOString()}'
QUALIFY ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY scored_at DESC) = 1
ORDER BY health_score ASC

-- health_score_history is an append-only streaming table.
-- Each pipeline refresh appends a new snapshot of scores.
-- QUALIFY ROW_NUMBER picks the latest score per asset before the requested time.`;

  async function handleShowSnapshot() {
    setSnapshotLoading(true);
    setSnapshotError(null);
    try {
      const ts = new Date(snapshotTimestamp).toISOString();
      const res = await api.getFleetSnapshot(ts);
      setSnapshotData(res.data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('404') || msg.includes('vacuum')) {
        setSnapshotError('No data available for this timestamp. Delta Lake history may have been vacuumed. Default retention is 30 days.');
      } else {
        setSnapshotError(msg);
      }
      setSnapshotData(null);
    } finally {
      setSnapshotLoading(false);
    }
  }

  function handleInvestigate(row: HealthScoreRow) {
    const scoredAt = new Date(row.scored_at);
    const from = new Date(scoredAt.getTime() - 30 * 60 * 1000).toISOString();
    const to = new Date(scoredAt.getTime() + 30 * 60 * 1000).toISOString();
    navigate(`/assets/${row.asset_id}?from=${from}&to=${to}&event_time=${scoredAt.toISOString()}`);
  }

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
          subtitle="$ (upcoming high-price windows)"
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

      {/* Fleet Snapshot (Time Travel) */}
      <section className="mb-8">
        <h3 className="font-heading text-lg font-semibold text-gray-700 mb-3">Fleet Snapshot (Point-in-Time)</h3>
        <div className="border border-gray-200 rounded-card bg-surface-card shadow-card p-4">
          <div className="flex items-center gap-4 mb-4 flex-wrap">
            <label className="text-sm text-gray-600">
              Show fleet state at
              <input
                type="datetime-local"
                aria-label="Snapshot timestamp"
                value={snapshotTimestamp}
                onChange={(e) => setSnapshotTimestamp(e.target.value)}
                className="ml-2 border border-gray-300 rounded px-2 py-1 text-sm"
              />
            </label>
            <button
              onClick={handleShowSnapshot}
              disabled={snapshotLoading}
              className="px-4 py-1.5 bg-databricks-primary text-white rounded text-sm disabled:opacity-50"
            >
              {snapshotLoading ? 'Loading...' : 'Show snapshot'}
            </button>
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={showCompare}
                onChange={(e) => setShowCompare(e.target.checked)}
                className="rounded"
              />
              Compare (then vs now)
            </label>
          </div>

          {snapshotError && (
            <div className="bg-red-50 border border-red-200 rounded p-3 mb-4 text-sm text-red-800">
              {snapshotError}
            </div>
          )}

          {snapshotData && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-gray-700 border-b-2 border-gray-200">
                    <th className="px-4 py-2 font-semibold">Asset</th>
                    <th className="px-4 py-2 font-semibold">Health (snapshot)</th>
                    {showCompare && <th className="px-4 py-2 font-semibold">Health (now)</th>}
                    <th className="px-4 py-2 font-semibold">Primary risk tag</th>
                    <th className="px-4 py-2 font-semibold">Risk description</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshotData.map((row) => {
                    const currentRow = (healthScores ?? []).find((h) => h.asset_id === row.asset_id);
                    const delta = currentRow
                      ? Math.abs((currentRow.health_score ?? 0) - (row.health_score ?? 0))
                      : 0;
                    const highlight = showCompare && delta > 0.1;
                    return (
                      <tr key={row.asset_id} className="border-t border-gray-200">
                        <td className="px-4 py-2 font-mono text-gray-700">{row.asset_id}</td>
                        <td className={`px-4 py-2 font-semibold ${healthColor(row.health_score)} ${highlight ? 'bg-yellow-100' : ''}`}>
                          {formatNumber(row.health_score, 2)}
                        </td>
                        {showCompare && (
                          <td className={`px-4 py-2 font-semibold ${healthColor(currentRow?.health_score)} ${highlight ? 'bg-yellow-100' : ''}`}>
                            {currentRow ? formatNumber(currentRow.health_score, 2) : '-'}
                          </td>
                        )}
                        <td className="px-4 py-2 text-gray-600">{row.primary_risk_tag ?? '-'}</td>
                        <td className="px-4 py-2 text-gray-600 max-w-md truncate">{row.risk_description ?? '-'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Show SQL collapsible */}
          <div className="mt-3">
            <button
              onClick={() => setShowSql(!showSql)}
              className="text-sm text-databricks-primary hover:underline"
            >
              {showSql ? 'Hide SQL' : 'Show SQL'}
            </button>
            {showSql && (
              <pre className="mt-2 bg-gray-900 text-gray-100 rounded p-3 text-xs overflow-x-auto">
                {snapshotSql}
              </pre>
            )}
          </div>
        </div>
      </section>

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
                <th className="px-4 py-3 font-semibold">Investigate</th>
              </tr>
            </thead>
            <tbody>
              {(healthScores ?? []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-gray-500">
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
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleInvestigate(row)}
                        className="px-3 py-1 text-sm bg-gray-100 text-gray-700 hover:bg-gray-200 rounded"
                      >
                        Investigate
                      </button>
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
                <th className="px-4 py-3 font-semibold">Revenue at risk ($)</th>
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
                      {formatDateTime(row.risk_window_start)} &rarr; {formatDateTime(row.risk_window_end)}
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
