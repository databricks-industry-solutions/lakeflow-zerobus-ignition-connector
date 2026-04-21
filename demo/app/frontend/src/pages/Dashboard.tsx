import { useCallback, useState, useEffect } from "react";
import { usePolling } from "../hooks/usePolling";
import { api } from "../services/api";
import type { DiagnosticData } from "../services/api";
import ThroughputChart from "../components/ThroughputChart";
import BigNumberCard from "../components/BigNumberCard";
import EventStream from "../components/EventStream";
import { formatNumber, formatLatency, latencyColor } from "../utils/format";

type WindowMinutes = 5 | 15 | 30 | 60;

export default function Dashboard() {
  const [windowMinutes, setWindowMinutes] = useState<WindowMinutes>(5);
  const [diagnostic, setDiagnostic] = useState<DiagnosticData | null>(null);
  const [diagnosticError, setDiagnosticError] = useState<string | null>(null);

  // Track backend errors from meta.error
  const [throughputError, setThroughputError] = useState<string | null>(null);
  const [latencyError, setLatencyError] = useState<string | null>(null);
  const [eventsError, setEventsError] = useState<string | null>(null);

  // Fetch throughput from both sources in parallel
  const rawTagsFetcher = useCallback(
    () =>
      api.getThroughput("raw_tags", windowMinutes).then((r) => {
        setThroughputError(r.meta?.error ?? null);
        return r.data;
      }),
    [windowMinutes],
  );
  const rawThroughputFetcher = useCallback(
    () =>
      api.getThroughput("raw_throughput", windowMinutes).then((r) => r.data),
    [windowMinutes],
  );
  const latencyFetcher = useCallback(
    () =>
      api.getLatency("raw_tags", windowMinutes).then((r) => {
        setLatencyError(r.meta?.error ?? null);
        return r.data;
      }),
    [windowMinutes],
  );
  const eventsFetcher = useCallback(
    () =>
      api.getEventsLatest(50).then((r) => {
        setEventsError(r.meta?.error ?? null);
        return r.data;
      }),
    [],
  );

  const throughputRaw = usePolling({
    fetcher: rawTagsFetcher,
    intervalMs: 5000,
  });
  const throughputCdf = usePolling({
    fetcher: rawThroughputFetcher,
    intervalMs: 5000,
  });
  const latency = usePolling({
    fetcher: latencyFetcher,
    intervalMs: 5000,
  });
  const events = usePolling({
    fetcher: eventsFetcher,
    intervalMs: 2000,
  });

  // Fetch diagnostic when throughput data is empty (to explain why)
  const isEmpty =
    !throughputRaw.loading &&
    (!throughputRaw.data || throughputRaw.data.length === 0);
  useEffect(() => {
    if (!isEmpty) {
      setDiagnostic(null);
      setDiagnosticError(null);
      return;
    }
    let cancelled = false;
    api
      .getDiagnostic()
      .then((r) => {
        if (!cancelled) {
          setDiagnostic(r.data ?? null);
          setDiagnosticError(r.meta?.error ?? null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDiagnostic(null);
          setDiagnosticError("Could not fetch diagnostic");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [isEmpty]);

  const latest = throughputRaw.data?.at(-1);
  const latencySeries = latency.data ?? [];
  const latestConnectorLatency = latencySeries.at(-1);
  const newestToOldestLatency = [...latencySeries].reverse();
  const latestE2eLatency = newestToOldestLatency.find(
    (point) =>
      point.avg_e2e_latency_ms != null && point.p99_e2e_latency_ms != null,
  );
  const latestDeltaToAppLatency = newestToOldestLatency.find(
    (point) => point.avg_delta_to_app_ms != null,
  );
  const windowSeconds = 5;
  const recordsPerSec =
    latest != null
      ? (Number(latest.records_after_sdt) || 0) / windowSeconds
      : null;

  // Compose empty-state / error message
  const backendError = throughputError || latencyError || eventsError;

  return (
    <div>
      {/* Fleet topology banner */}
      <div className="flex items-center gap-3 bg-gray-50 border border-gray-200 rounded-card px-4 py-3 mb-6 text-sm text-gray-700">
        <span className="flex h-2 w-2 rounded-full bg-brand-green animate-pulse" aria-hidden />
        <span>
          <strong>Simulating AGL Energy fleet</strong> &mdash; 7 sites
          (Torrens Island 20, Wandoan 8, Callide 6, Liddell 5, Broken Hill 5, Tomago 4, Dalrymple 3)
          &mdash; <strong>51 BESS units</strong>, 1,348 tags, ~2,700 events/sec into Databricks via Zerobus
        </span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <h2 className="font-heading text-2xl font-semibold text-gray-900">
          Dashboard
        </h2>
        <div className="flex items-center gap-4">
          {/* Time window selector — segmented control */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Window:</span>
            <div className="flex rounded-card border border-gray-200 overflow-hidden bg-surface-card shadow-card">
              {([5, 15, 30, 60] as WindowMinutes[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setWindowMinutes(m)}
                  className={`px-2.5 py-2 text-xs font-medium transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-databricks-primary focus-visible:ring-inset ${
                    windowMinutes === m
                      ? "bg-databricks-primary text-white"
                      : "bg-transparent text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                  }`}
                >
                  {m}m
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Error / empty-state banner */}
      {backendError && (
        <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-card p-4 mb-6 text-sm text-red-800">
          <span
            className="flex h-5 w-5 flex-shrink-0 rounded-full bg-red-400 mt-0.5"
            aria-hidden
          />
          <div>
            <strong>Query error:</strong> {backendError}
          </div>
        </div>
      )}
      {isEmpty && !backendError && (
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-card p-4 mb-6 text-sm text-amber-800">
          <span
            className="flex h-5 w-5 flex-shrink-0 rounded-full bg-amber-300 mt-0.5"
            aria-hidden
          />
          <div>
            <strong>No events in the last {windowMinutes} minutes.</strong> Try
            a longer window or generate new events (e.g.{" "}
            <code className="text-xs bg-amber-100 px-1.5 py-0.5 rounded">
              make simulate-83
            </code>
            ).
            {diagnostic && (
              <span className="block mt-1 text-amber-700">
                Table has <strong>{diagnostic.total_rows}</strong> total rows;{" "}
                <strong>{diagnostic.rows_last_10_min}</strong> in the last 10
                min.
                {diagnostic.newest_event && (
                  <>
                    {" "}
                    Newest event:{" "}
                    <code className="text-xs">{diagnostic.newest_event}</code>
                  </>
                )}
              </span>
            )}
            {diagnosticError && (
              <span className="block mt-1 text-amber-700">
                Diagnostic failed: {diagnosticError}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Throughput cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <BigNumberCard
          label="Records/sec"
          value={recordsPerSec != null ? formatNumber(recordsPerSec, 0) : "-"}
          subtitle="Ingested (post-SDT)"
        />
        <BigNumberCard
          label="Active tags"
          value={latest ? formatNumber(latest.tags_active, 0) : "-"}
        />
        <BigNumberCard
          label="Active assets"
          value={
            events.data
              ? formatNumber(
                  new Set(events.data.map((e) => e.asset_id)).size,
                  0,
                )
              : "-"
          }
        />
        <BigNumberCard
          label="SDT compression"
          value={
            latest
              ? latest.sdt_enabled
                ? Number(latest.sdt_compression_ratio) > 0
                  ? `${Number(latest.sdt_compression_ratio) < 0.1
                      ? Number(latest.sdt_compression_ratio).toFixed(3)
                      : formatNumber(Number(latest.sdt_compression_ratio), 1)}%`
                  : "On"
                : "Off"
              : "-"
          }
          subtitle={
            latest?.sdt_enabled
              ? "Events suppressed by SDT"
              : "Gateway: SDT off"
          }
          colorClass={latest?.sdt_enabled ? "text-brand-green" : "text-databricks-primary"}
        />
      </div>

      {/* Latency cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <BigNumberCard
          label="Tag → gateway ingest"
          value={
            latestConnectorLatency
              ? `${formatNumber(latestConnectorLatency.avg_latency_ms, 0)}ms`
              : "-"
          }
          subtitle="Inside connector path only"
          colorClass={
            latestConnectorLatency
              ? latencyColor(latestConnectorLatency.avg_latency_ms)
              : "text-databricks-primary"
          }
        />
        {latestE2eLatency ? (
          <>
            <BigNumberCard
              label="Avg time to insight"
              value={formatLatency(latestE2eLatency.avg_e2e_latency_ms)}
              subtitle="Ignition → Delta commit (via raw_throughput)"
              colorClass={latencyColor(latestE2eLatency.avg_e2e_latency_ms)}
            />
            <BigNumberCard
              label="P99 time to insight"
              value={formatLatency(latestE2eLatency.p99_e2e_latency_ms)}
              subtitle="Ignition → Delta commit (via raw_throughput)"
            />
          </>
        ) : (
          <>
            <BigNumberCard
              label="Avg time to insight"
              value="-"
              subtitle="Needs CDF commit timestamps"
            />
            <BigNumberCard
              label="P99 time to insight"
              value="-"
              subtitle="Needs CDF commit timestamps"
            />
          </>
        )}
        <BigNumberCard
          label="Delta → app read"
          value={
            latestDeltaToAppLatency?.avg_delta_to_app_ms != null
              ? formatLatency(latestDeltaToAppLatency.avg_delta_to_app_ms)
              : "-"
          }
          subtitle="Commit visibility freshness (via raw_throughput)"
          colorClass={
            latestDeltaToAppLatency?.avg_delta_to_app_ms != null
              ? latencyColor(latestDeltaToAppLatency.avg_delta_to_app_ms)
              : "text-databricks-primary"
          }
        />
      </div>
      <p className="text-gray-500 text-sm mb-6">
        <strong>Time to insight</strong> = full path from tag event in Ignition
        to Delta commit (from <code>raw_throughput</code> CDF{" "}
        <code>_commit_timestamp</code>). <strong>Tag → gateway ingest</strong>
        is only connector-side timestamping (excludes Zerobus and Delta commit).{" "}
        <strong>Delta → app read</strong>
        is commit-to-query freshness at dashboard read time.
      </p>

      {/* Throughput chart */}
      <div className="mb-6">
        <ThroughputChart
          rawTagsData={throughputRaw.data ?? []}
          rawThroughputData={throughputCdf.data ?? []}
        />
      </div>

      {/* Live event stream */}
      <EventStream events={events.data ?? []} />
    </div>
  );
}
