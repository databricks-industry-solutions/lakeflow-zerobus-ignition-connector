import { useState, useCallback, useMemo } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from "recharts";
import { usePolling } from "../hooks/usePolling";
import { api } from "../services/api";
import type { Asset, TagHistory } from "../services/api";
import { qualityLabel, formatNumber, formatTimestamp } from "../utils/format";
import TimeRangeSelector from "../components/TimeRangeSelector";
import type { TimeRange } from "../components/TimeRangeSelector";

const WIND_TAGS = [
  "generator/power_kw",
  "rotor/wind_speed_ms",
  "nacelle/temperature_c",
  "grid/frequency_hz",
];
const BESS_TAGS = [
  "telemetry/soc_pct",
  "telemetry/activepower_mw",
  "thermal/maxracktemp_c",
  "telemetry/frequency_hz",
];

const CHART_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444"];

const PRESET_MINUTES: Record<string, number> = {
  "5m": 5,
  "15m": 15,
  "1h": 60,
  "6h": 360,
  "24h": 1440,
  "7d": 10080,
  "30d": 43200,
};

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
  const params = useParams<{ id: string; assetId: string }>();
  const id = params.id ?? params.assetId;
  const [searchParams, setSearchParams] = useSearchParams();
  const [showRaw, setShowRaw] = useState(false);

  // Read initial time range from URL params
  const urlFrom = searchParams.get("from");
  const urlTo = searchParams.get("to");
  const urlRange = searchParams.get("range");
  const urlEventTime = searchParams.get("event_time");

  const initialTimeRange: TimeRange = useMemo(() => {
    if (urlFrom && urlTo) {
      return { from: urlFrom, to: urlTo, preset: "Custom" };
    }
    const preset = urlRange ?? "5m";
    const minutes = PRESET_MINUTES[preset] ?? 5;
    const now = new Date();
    return {
      from: new Date(now.getTime() - minutes * 60 * 1000).toISOString(),
      to: now.toISOString(),
      preset,
    };
  }, [urlFrom, urlTo, urlRange]);

  const [timeRange, setTimeRange] = useState<TimeRange>(initialTimeRange);

  const handleTimeRangeChange = useCallback(
    (value: TimeRange) => {
      setTimeRange(value);
      const params = new URLSearchParams();
      if (value.preset && value.preset !== "custom") {
        params.set("range", value.preset);
      } else {
        params.set("from", value.from);
        params.set("to", value.to);
      }
      if (urlEventTime) {
        params.set("event_time", urlEventTime);
      }
      setSearchParams(params, { replace: true });
    },
    [setSearchParams, urlEventTime],
  );

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
    () => (asset?.asset_type === "battery_bess" ? BESS_TAGS : WIND_TAGS),
    [asset?.asset_type],
  );

  // Determine if we should use range-based or preset-based query
  const isCustomRange = timeRange.preset === "Custom" || !!(urlFrom && urlTo);
  const rangeMinutes = timeRange.preset
    ? PRESET_MINUTES[timeRange.preset] ?? 5
    : 5;

  // Single query for all tags - filter client-side for charts
  const allTagsFetcher = useCallback(
    () => {
      if (!id) return Promise.resolve([]);
      if (isCustomRange) {
        return api
          .getAssetTagsRange(id, timeRange.from, timeRange.to)
          .then((r) => r.data);
      }
      return api.getAssetTags(id, undefined, rangeMinutes).then((r) => r.data);
    },
    [id, isCustomRange, timeRange.from, timeRange.to, rangeMinutes],
  );
  const {
    data: allTags,
    loading: tagsLoading,
    error: tagsError,
  } = usePolling<TagHistory[]>({
    fetcher: allTagsFetcher,
    intervalMs: isCustomRange ? 0 : 5000,
    enabled: !!id,
  });

  // Build chart data per tag from the single query result
  const chartDataByTag = useMemo(() => {
    const byTag: Record<
      string,
      { time: string; value: number; sdt: boolean }[]
    > = {};
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
    const latest = new Map<string, TagHistory>();
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

  // CSV download handler
  const handleDownloadCsv = useCallback(async () => {
    if (!id) return;
    try {
      await api.exportAssetTagsCsv(id, timeRange.from, timeRange.to);
    } catch {
      // Silently fail for now -- could add toast later
    }
  }, [id, timeRange]);

  // Event time reference line for forensics mode
  const eventTimeRef = urlEventTime
    ? formatTimestamp(urlEventTime)
    : null;

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
              {asset
                ? `${asset.asset_name} - ${asset.site_name}`
                : "Asset detail"}
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
      <div className="flex items-center gap-4 mb-4 flex-wrap">
        <TimeRangeSelector value={timeRange} onChange={handleTimeRangeChange} />
        <button
          onClick={handleDownloadCsv}
          className="px-3 py-1 rounded text-sm bg-gray-100 text-gray-600 hover:text-gray-800 hover:bg-gray-200"
        >
          Download CSV
        </button>
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

      {/* Loading indicator */}
      {tagsLoading && (
        <div className="text-sm text-gray-500 mb-2">Loading tag data...</div>
      )}

      {/* Error banner */}
      {tagsError && (
        <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-card p-4 mb-4 text-sm text-red-800">
          <span
            className="flex h-5 w-5 flex-shrink-0 rounded-full bg-red-400 mt-0.5"
            aria-hidden
          />
          <div>
            <strong>Query error:</strong> {tagsError.message}
            {tagsError.message?.includes("TABLE_OR_VIEW_NOT_FOUND") && (
              <p className="mt-1 text-red-600">
                The SDP pipeline may not have run yet. Check that the pipeline is running
                in Workflows &gt; Lakeflow Pipelines.
              </p>
            )}
          </div>
        </div>
      )}

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
                        backgroundColor: "#ffffff",
                        border: "1px solid #e5e7eb",
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
                                : "#4B5563";
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
                    {eventTimeRef && (
                      <ReferenceLine
                        x={eventTimeRef}
                        stroke="#EF4444"
                        strokeDasharray="5 5"
                        label={{ value: "Event", fill: "#EF4444", fontSize: 11 }}
                      />
                    )}
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
                    className={`border-b border-gray-200/50 hover:bg-gray-100/30 ${
                      urlEventTime && t.quality !== 192
                        ? "bg-red-50"
                        : ""
                    }`}
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
