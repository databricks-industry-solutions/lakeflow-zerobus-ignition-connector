import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { ThroughputMetric } from "../services/api";
import { formatTimestamp } from "../utils/format";

/** Backend aggregates in 5-second windows; divide by this to get events/sec. */
const WINDOW_SECONDS = 5;

interface ChartDatum {
  time: string;
  rawTagsPerSec: number;
  rawThroughputPerSec: number | null;
  rawTagsRaw: number;
  rawTagsPostSdt: number;
  rawTagsRawPerSec: number;
  sdtRatio: number | null;
}

interface ThroughputChartProps {
  rawTagsData: ThroughputMetric[];
  rawThroughputData: ThroughputMetric[];
}

type SeriesKey = "rawEstimate" | "postSdt" | "rawThroughput";

interface SeriesConfig {
  key: SeriesKey;
  dataKey: string;
  label: string;
  color: string;
  dashed?: boolean;
  /** Only shown when SDT compression is detected */
  sdtOnly?: boolean;
}

const SERIES: SeriesConfig[] = [
  {
    key: "rawEstimate",
    dataKey: "rawTagsRawPerSec",
    label: "Raw estimate",
    color: "#FF3621",
    dashed: true,
    sdtOnly: true,
  },
  {
    key: "postSdt",
    dataKey: "rawTagsPerSec",
    label: "raw_tags (post-SDT)",
    color: "#10B981",
  },
  {
    key: "rawThroughput",
    dataKey: "rawThroughputPerSec",
    label: "raw_throughput (CDF)",
    color: "#3B82F6",
  },
];

/** When SDT is off, relabel the post-SDT series */
const SERIES_NO_SDT: SeriesConfig[] = [
  {
    key: "postSdt",
    dataKey: "rawTagsPerSec",
    label: "raw_tags",
    color: "#FF3621",
  },
  {
    key: "rawThroughput",
    dataKey: "rawThroughputPerSec",
    label: "raw_throughput (CDF)",
    color: "#3B82F6",
  },
];

function formatSdtPct(pct: number | null | undefined): string {
  const r = pct != null ? Number(pct) : null;
  if (r == null || r <= 0) return "0%";
  const formatted = r < 0.1 ? r.toFixed(3) : r.toFixed(1);
  return `${formatted}% suppressed`;
}

export default function ThroughputChart({
  rawTagsData,
  rawThroughputData,
}: ThroughputChartProps) {
  const [expanded, setExpanded] = useState(false);
  const [hidden, setHidden] = useState<Set<SeriesKey>>(new Set());

  // Index raw_throughput data by window_start for merging
  const cdfByTime = new Map<string, ThroughputMetric>();
  for (const d of rawThroughputData) {
    cdfByTime.set(d.window_start, d);
  }

  const chartData: ChartDatum[] = rawTagsData.map((d) => {
    const raw = Number(d.records_raw) || 0;
    const postSdt = Number(d.records_after_sdt) || 0;
    const cdf = cdfByTime.get(d.window_start);
    const cdfPostSdt = cdf ? Number(cdf.records_after_sdt) || 0 : null;
    return {
      time: formatTimestamp(d.window_start),
      rawTagsPerSec: postSdt / WINDOW_SECONDS,
      rawThroughputPerSec:
        cdfPostSdt != null ? cdfPostSdt / WINDOW_SECONDS : null,
      rawTagsRaw: raw,
      rawTagsPostSdt: postSdt,
      rawTagsRawPerSec: raw / WINDOW_SECONDS,
      sdtRatio:
        d.sdt_compression_ratio != null
          ? Number(d.sdt_compression_ratio)
          : null,
    };
  });

  const hasSdtCompression = rawTagsData.some((d) => d.sdt_enabled === true)
    || chartData.some((d) => d.rawTagsRaw > d.rawTagsPostSdt);

  const seriesList = hasSdtCompression ? SERIES : SERIES_NO_SDT;
  const visibleSeries = seriesList.filter((s) => !hidden.has(s.key));

  const toggleSeries = (key: SeriesKey) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        // Don't allow hiding all series
        if (next.size < seriesList.length - 1) {
          next.add(key);
        }
      }
      return next;
    });
  };

  const chartHeight = expanded ? "100%" : 250;

  return (
    <>
      {expanded && (
        <div
          className="fixed inset-0 bg-black/40 z-40"
          onClick={() => setExpanded(false)}
        />
      )}
    <div className={`bg-white border border-gray-200 rounded-card p-6 shadow-card transition-all duration-300 ${expanded ? "fixed inset-6 z-50 overflow-auto flex flex-col" : ""}`}>

      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-heading font-semibold text-gray-700">
          Throughput (events/sec)
        </h3>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">
            {hasSdtCompression
              ? "raw_tags shows post-SDT; raw estimate from compression ratio"
              : "Overlaid: raw_tags (Zerobus) vs raw_throughput (CDF pipeline)"}
          </span>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-gray-400 hover:text-gray-700 border border-gray-200 rounded px-2 py-1 transition-colors"
            title={expanded ? "Collapse chart" : "Expand chart"}
          >
            {expanded ? "\u2716 Close" : "\u2922 Expand"}
          </button>
        </div>
      </div>

      {/* Series toggles */}
      <div className="flex flex-wrap gap-3 mb-3">
        {seriesList.map((s) => {
          const isHidden = hidden.has(s.key);
          return (
            <button
              key={s.key}
              type="button"
              onClick={() => toggleSeries(s.key)}
              className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border transition-all duration-200 ${
                isHidden
                  ? "border-gray-200 text-gray-400 bg-gray-50"
                  : "border-gray-300 text-gray-700 bg-white shadow-sm"
              }`}
            >
              <span
                className="inline-block w-2.5 h-2.5 rounded-full transition-opacity"
                style={{
                  backgroundColor: s.color,
                  opacity: isHidden ? 0.3 : 1,
                }}
              />
              {s.label}
            </button>
          );
        })}
      </div>

      <ResponsiveContainer width="100%" height={chartHeight}>
        <AreaChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="time" stroke="#9ca3af" fontSize={12} />
          <YAxis stroke="#9ca3af" fontSize={12} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#ffffff",
              border: "1px solid #e5e7eb",
              borderRadius: "0.5rem",
              boxShadow:
                "0 4px 6px -1px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.06)",
            }}
            labelStyle={{ color: "#374151" }}
            content={({ active, payload, label }) => {
              if (!active || !payload?.length || !label) return null;
              const d = payload[0].payload as ChartDatum;
              return (
                <div className="rounded px-3 py-2 min-w-[200px]">
                  <div className="text-gray-700 font-medium border-b border-gray-200 pb-1 mb-2">
                    {label}
                  </div>
                  <div className="text-gray-600 text-sm space-y-0.5">
                    {hasSdtCompression && !hidden.has("rawEstimate") && (
                      <div>
                        <span style={{ color: "#FF3621" }}>
                          Raw estimate:
                        </span>{" "}
                        <span className="text-gray-900 font-semibold">
                          {d.rawTagsRawPerSec.toLocaleString(undefined, {
                            maximumFractionDigits: 0,
                          })}
                          /sec
                        </span>
                      </div>
                    )}
                    {!hidden.has("postSdt") && (
                      <div>
                        <span
                          style={{
                            color: hasSdtCompression ? "#10B981" : "#FF3621",
                          }}
                        >
                          raw_tags{hasSdtCompression ? " (post-SDT)" : ""}:
                        </span>{" "}
                        <span className="text-gray-900 font-semibold">
                          {d.rawTagsPerSec.toLocaleString(undefined, {
                            maximumFractionDigits: 0,
                          })}
                          /sec
                        </span>
                      </div>
                    )}
                    {!hidden.has("rawThroughput") && (
                      <div>
                        <span style={{ color: "#3B82F6" }}>
                          raw_throughput:
                        </span>{" "}
                        <span className="text-gray-900 font-semibold">
                          {d.rawThroughputPerSec != null
                            ? `${d.rawThroughputPerSec.toLocaleString(undefined, { maximumFractionDigits: 0 })}/sec`
                            : "-"}
                        </span>
                      </div>
                    )}
                    <div className="pt-1 border-t border-gray-200 mt-1">
                      SDT:{" "}
                      <span className="text-gray-900 font-medium">
                        {formatSdtPct(d.sdtRatio)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            }}
          />
          <Legend />
          {visibleSeries.map((s) => (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.dataKey}
              name={s.label}
              stroke={s.color}
              fill={s.color}
              fillOpacity={s.dashed ? 0.1 : 0.2}
              strokeDasharray={s.dashed ? "4 2" : undefined}
              connectNulls={s.key === "rawThroughput"}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
    </>
  );
}
