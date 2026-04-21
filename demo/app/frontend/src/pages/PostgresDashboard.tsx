import { useCallback, useState, useEffect } from "react";
import { usePolling } from "../hooks/usePolling";
import { api } from "../services/api";
import type { PostgresDiagnosticData } from "../services/api";
import ThroughputChart from "../components/ThroughputChart";
import BigNumberCard from "../components/BigNumberCard";
import EventStream from "../components/EventStream";
import { formatNumber, latencyColor } from "../utils/format";

type WindowMinutes = 5 | 15 | 30 | 60;

export default function PostgresDashboard() {
  const [windowMinutes, setWindowMinutes] = useState<WindowMinutes>(5);
  const [health, setHealth] = useState<{
    status: string;
    error?: string;
  } | null>(null);
  const [diagnostic, setDiagnostic] = useState<PostgresDiagnosticData | null>(
    null,
  );

  // Track backend errors from meta.error
  const [throughputError, setThroughputError] = useState<string | null>(null);
  const [latencyError, setLatencyError] = useState<string | null>(null);
  const [eventsError, setEventsError] = useState<string | null>(null);

  // Check health on mount
  useEffect(() => {
    api.postgres
      .getHealth()
      .then((r) => {
        setHealth(r.data);
      })
      .catch(() => {
        setHealth({ status: "error", error: "Failed to check health" });
      });
  }, []);

  const throughputFetcher = useCallback(
    () =>
      api.postgres.getThroughput(windowMinutes).then((r) => {
        setThroughputError(r.meta?.error ?? null);
        return r.data;
      }),
    [windowMinutes],
  );
  const latencyFetcher = useCallback(
    () =>
      api.postgres.getLatency(windowMinutes).then((r) => {
        setLatencyError(r.meta?.error ?? null);
        return r.data;
      }),
    [windowMinutes],
  );
  const eventsFetcher = useCallback(
    () =>
      api.postgres.getEventsLatest(50).then((r) => {
        setEventsError(r.meta?.error ?? null);
        return r.data;
      }),
    [],
  );

  const isConfigured = health?.status !== "not_configured";

  const throughput = usePolling({
    fetcher: throughputFetcher,
    intervalMs: 5000,
    enabled: isConfigured,
  });
  const latency = usePolling({
    fetcher: latencyFetcher,
    intervalMs: 5000,
    enabled: isConfigured,
  });
  const events = usePolling({
    fetcher: eventsFetcher,
    intervalMs: 2000,
    enabled: isConfigured,
  });

  // Fetch diagnostic when throughput data is empty
  const isEmpty =
    isConfigured &&
    !throughput.loading &&
    (!throughput.data || throughput.data.length === 0);
  useEffect(() => {
    if (!isEmpty || !isConfigured) {
      setDiagnostic(null);
      return;
    }
    api.postgres
      .getDiagnostic()
      .then((r) => setDiagnostic(r.data ?? null))
      .catch(() => setDiagnostic(null));
  }, [isEmpty, isConfigured]);

  const latest = throughput.data?.at(-1);
  const latestLatency = latency.data?.at(-1);
  const windowSeconds = 5;
  const recordsPerSec =
    latest != null
      ? (Number(latest.records_after_sdt) || 0) / windowSeconds
      : null;

  const backendError = throughputError || latencyError || eventsError;

  // Not configured banner
  if (!isConfigured) {
    return (
      <div>
        <h2 className="font-heading text-2xl font-semibold text-gray-900 mb-6">
          PostgreSQL (Lakebase) Dashboard
        </h2>
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-card p-4 text-sm text-amber-800">
          <span
            className="flex h-5 w-5 flex-shrink-0 rounded-full bg-amber-300 mt-0.5"
            aria-hidden
          />
          <div>
            <strong>PostgreSQL (Lakebase) not configured.</strong> Set the
            following environment variables in your Databricks App:
            <ul className="mt-2 list-disc list-inside text-amber-700">
              <li>
                <code className="text-xs bg-amber-100 px-1 py-0.5 rounded">
                  LAKEBASE_HOST
                </code>
              </li>
              <li>
                <code className="text-xs bg-amber-100 px-1 py-0.5 rounded">
                  LAKEBASE_DATABASE
                </code>
              </li>
              <li>
                <code className="text-xs bg-amber-100 px-1 py-0.5 rounded">
                  LAKEBASE_USER
                </code>
              </li>
              <li>
                <code className="text-xs bg-amber-100 px-1 py-0.5 rounded">
                  LAKEBASE_PASSWORD
                </code>
              </li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <h2 className="font-heading text-2xl font-semibold text-gray-900">
          PostgreSQL (Lakebase) Dashboard
        </h2>
        <div className="flex items-center gap-4">
          {/* Connection status indicator */}
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                health?.status === "healthy"
                  ? "bg-green-500"
                  : health?.status === "unhealthy"
                    ? "bg-red-500"
                    : "bg-amber-500"
              }`}
            />
            <span className="text-sm text-gray-600">
              {health?.status === "healthy"
                ? "Connected"
                : health?.status === "unhealthy"
                  ? "Disconnected"
                  : "Unknown"}
            </span>
          </div>
          {/* Time window selector */}
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

      {/* Error banner */}
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

      {/* Empty state banner */}
      {isEmpty && !backendError && (
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-card p-4 mb-6 text-sm text-amber-800">
          <span
            className="flex h-5 w-5 flex-shrink-0 rounded-full bg-amber-300 mt-0.5"
            aria-hidden
          />
          <div>
            <strong>No events in the last {windowMinutes} minutes.</strong>{" "}
            Ensure the Ignition gateway is configured with PostgreSQL sink
            enabled.
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
          </div>
        </div>
      )}

      {/* Big number cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <BigNumberCard
          label="Records/sec"
          value={recordsPerSec != null ? formatNumber(recordsPerSec, 0) : "-"}
          subtitle="PostgreSQL (Lakebase)"
        />
        <BigNumberCard
          label="Active tags"
          value={latest ? formatNumber(latest.tags_active, 0) : "-"}
        />
        <BigNumberCard
          label="Avg latency"
          value={
            latestLatency
              ? `${formatNumber(latestLatency.avg_latency_ms, 0)}ms`
              : "-"
          }
          subtitle="Tag -> PostgreSQL"
          colorClass={
            latestLatency
              ? latencyColor(latestLatency.avg_latency_ms)
              : "text-databricks-primary"
          }
        />
        <BigNumberCard
          label="P99 latency"
          value={
            latestLatency
              ? `${formatNumber(latestLatency.p99_latency_ms ?? 0, 0)}ms`
              : "-"
          }
          subtitle="Tag -> PostgreSQL"
        />
        <BigNumberCard
          label="SDT compression"
          value={
            latest
              ? Number(latest.sdt_compression_ratio) > 1
                ? `${formatNumber(Number(latest.sdt_compression_ratio), 1)}:1`
                : "Off"
              : "-"
          }
          colorClass="text-brand-green"
        />
      </div>

      <p className="text-gray-500 text-sm mb-6">
        <strong>Lakebase metrics</strong> - direct PostgreSQL read path for
        low-latency OLTP queries. Latency shown is from tag event to PostgreSQL
        insert (in-process + network).
      </p>

      {/* Throughput chart */}
      <div className="mb-6">
        <ThroughputChart
          rawTagsData={throughput.data ?? []}
          rawThroughputData={[]}
        />
      </div>

      {/* Live event stream */}
      <EventStream events={events.data ?? []} />
    </div>
  );
}
