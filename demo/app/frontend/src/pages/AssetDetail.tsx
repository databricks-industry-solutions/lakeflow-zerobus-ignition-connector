import { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import type { Asset, TagHistory } from '../services/api';
import { qualityLabel, formatNumber, formatTimestamp } from '../utils/format';

const WIND_TAGS = [
  'generator/power_kw',
  'rotor/wind_speed_ms',
  'nacelle/temperature_c',
  'grid/frequency_hz',
];
const BESS_TAGS = [
  'battery/soc_pct',
  'battery/charge_rate_kw',
  'battery/temperature_c',
  'inverter/power_kw',
];

const CHART_COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444'];

type TimeRange = 5 | 15 | 60;

function ChartSkeleton() {
  return (
    <div className="bg-surface-card border border-gray-200 rounded-card p-4 animate-pulse shadow-card">
      <div className="h-4 w-32 bg-gray-100 rounded mb-4" />
      <div className="h-[200px] bg-gray-100/50 rounded" />
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="bg-surface-card border border-gray-200 rounded-card p-4 animate-pulse shadow-card">
      <div className="h-4 w-20 bg-gray-100 rounded mb-4" />
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex gap-4 py-2">
          <div className="h-3 w-40 bg-gray-100 rounded" />
          <div className="h-3 w-16 bg-gray-100 rounded ml-auto" />
          <div className="h-3 w-12 bg-gray-100 rounded" />
          <div className="h-3 w-24 bg-gray-100 rounded" />
        </div>
      ))}
    </div>
  );
}

export default function AssetDetail() {
  const { id } = useParams<{ id: string }>();
  const [range, setRange] = useState<TimeRange>(5);
  const [showRaw, setShowRaw] = useState(false);

  const assetFetcher = useCallback(
    () => (id ? api.getAsset(id).then((r) => r.data) : Promise.resolve(null)),
    [id],
  );
  const { data: asset, loading: assetLoading } = usePolling<Asset | null>({
    fetcher: assetFetcher,
    intervalMs: 10000,
    enabled: !!id,
  });

  const trendTags = useMemo(
    () => (asset?.asset_type === 'battery_bess' ? BESS_TAGS : WIND_TAGS),
    [asset?.asset_type],
  );

  // Single query for all tags - filter client-side for charts
  const allTagsFetcher = useCallback(
    () =>
      id
        ? api.getAssetTags(id, undefined, range).then((r) => r.data)
        : Promise.resolve([]),
    [id, range],
  );
  const { data: allTags, loading: tagsLoading } = usePolling<TagHistory[]>({
    fetcher: allTagsFetcher,
    intervalMs: 5000,
    enabled: !!id,
  });

  // Build chart data per tag from the single query result
  const chartDataByTag = useMemo(() => {
    const byTag: Record<string, { time: string; value: number; sdt: boolean }[]> = {};
    for (const tag of trendTags) {
      byTag[tag] = (allTags ?? [])
        .filter((t) => t.tag_name === tag)
        .map((t) => ({
          time: formatTimestamp(t.event_timestamp),
          value: t.tag_value,
          sdt: t.sdt_compressed,
        }));
    }
    return byTag;
  }, [allTags, trendTags]);

  // Build tag table - latest value per unique tag
  const tagTable = useMemo(() => {
    const latest = new Map<
      string,
      TagHistory
    >();
    for (const t of allTags ?? []) {
      const existing = latest.get(t.tag_name);
      if (!existing || t.event_timestamp > existing.event_timestamp) {
        latest.set(t.tag_name, t);
      }
    }
    return Array.from(latest.values()).sort((a, b) =>
      a.tag_name.localeCompare(b.tag_name),
    );
  }, [allTags]);

  if (!id) return <p className="text-gray-600">No asset selected.</p>;

  return (
    <div>
      {/* Metadata header */}
      <div className="mb-6">
        {assetLoading && !asset ? (
          <div className="animate-pulse">
            <div className="h-7 w-64 bg-gray-100 rounded mb-2" />
            <div className="h-4 w-48 bg-gray-100 rounded" />
          </div>
        ) : (
          <>
            <h2 className="font-heading text-2xl font-semibold text-gray-900">
              {asset ? `${asset.asset_name} - ${asset.site_name}` : 'Asset detail'}
            </h2>
            {asset && (
              <div className="flex gap-4 text-sm text-gray-600 mt-1">
                <span>Type: {asset.asset_type}</span>
                {asset.capacity_mw != null && (
                  <span>Capacity: {formatNumber(asset.capacity_mw, 1)} MW</span>
                )}
                <span>{asset.tag_count} tags</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4 mb-4">
        <div className="flex gap-2">
          {([5, 15, 60] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1 rounded text-sm ${
                range === r
                  ? 'bg-databricks-primary text-white'
                  : 'bg-gray-100 text-gray-600 hover:text-gray-800'
              }`}
            >
              {r === 60 ? '1 hour' : `${r} min`}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={showRaw}
            onChange={(e) => setShowRaw(e.target.checked)}
            className="rounded"
          />
          Show raw vs compressed
        </label>
      </div>

      {/* Trend charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {tagsLoading && !allTags
          ? Array.from({ length: 4 }).map((_, i) => <ChartSkeleton key={i} />)
          : trendTags.map((tag, idx) => (
              <div
                key={tag}
                className="bg-surface-card border border-gray-200 rounded-card p-4 shadow-card"
              >
                <h4 className="text-sm text-gray-600 mb-2">{tag}</h4>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartDataByTag[tag] ?? []}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="time" stroke="#9CA3AF" fontSize={11} />
                    <YAxis stroke="#9CA3AF" fontSize={11} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#ffffff',
                        border: '1px solid #e5e7eb',
                      }}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="value"
                      name="Value"
                      stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                      dot={
                        showRaw
                          ? (props: Record<string, unknown>) => {
                              const { cx, cy, payload } = props as {
                                cx: number;
                                cy: number;
                                payload: { sdt: boolean };
                              };
                              const color = payload.sdt
                                ? CHART_COLORS[idx % CHART_COLORS.length]
                                : '#4B5563';
                              return (
                                <circle
                                  key={`${cx}-${cy}`}
                                  cx={cx}
                                  cy={cy}
                                  r={3}
                                  fill={color}
                                  opacity={payload.sdt ? 1 : 0.4}
                                />
                              );
                            }
                          : false
                      }
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ))}
      </div>

      {/* Tag table */}
      {tagsLoading && !allTags ? (
        <TableSkeleton />
      ) : (
        <div className="bg-surface-card border border-gray-200 rounded-card p-4 shadow-card">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">All tags</h3>
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-600 border-b border-gray-200">
                  <th className="text-left py-2 px-2">Tag name</th>
                  <th className="text-right py-2 px-2">Current value</th>
                  <th className="text-left py-2 px-2">Quality</th>
                  <th className="text-left py-2 px-2">Last updated</th>
                  <th className="text-center py-2 px-2">SDT</th>
                </tr>
              </thead>
              <tbody>
                {tagTable.map((t) => (
                  <tr
                    key={t.tag_name}
                    className="border-b border-gray-200/50 hover:bg-gray-100/30"
                  >
                    <td className="py-1.5 px-2 text-gray-700">{t.tag_name}</td>
                    <td className="py-1.5 px-2 text-right text-gray-900">
                      {formatNumber(t.tag_value)}
                    </td>
                    <td className="py-1.5 px-2 text-gray-600">
                      {qualityLabel(t.quality)}
                    </td>
                    <td className="py-1.5 px-2 text-gray-600">
                      {formatTimestamp(t.event_timestamp)}
                    </td>
                    <td className="py-1.5 px-2 text-center">
                      {t.sdt_compressed ? (
                        <span className="text-brand-green">&#10003;</span>
                      ) : (
                        <span className="text-gray-600">&#10007;</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
