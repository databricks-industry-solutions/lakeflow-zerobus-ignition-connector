import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "../../pages/Dashboard";
import { api } from "../../services/api";

// Mock recharts to avoid rendering issues in jsdom
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: unknown }) => (
    <div data-testid="responsive-container">{children as any}</div>
  ),
  AreaChart: ({ children }: { children: unknown }) => (
    <div data-testid="area-chart">{children as any}</div>
  ),
  Area: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
}));

vi.mock("../../services/api", () => ({
  api: {
    getThroughput: vi.fn(),
    getLatency: vi.fn(),
    getEventsLatest: vi.fn(),
    getDiagnostic: vi.fn(),
  },
}));

const meta = { timestamp: "2026-03-26T00:00:00Z", query_time_ms: 1 };

describe("Dashboard page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getThroughput)
      .mockResolvedValueOnce({ data: [], meta })
      .mockResolvedValueOnce({ data: [], meta });
    vi.mocked(api.getLatency).mockResolvedValue({ data: [], meta });
    vi.mocked(api.getEventsLatest).mockResolvedValue({ data: [], meta });
    vi.mocked(api.getDiagnostic).mockResolvedValue({
      data: {
        total_rows: "0",
        rows_last_10_min: "0",
        oldest_event: null,
        newest_event: null,
        warehouse_now: "2026-03-26T00:00:00Z",
      },
      meta,
    });
  });

  it("renders throughput chart, latency panel, and event stream sections", async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Active tags")).toBeInTheDocument();
    expect(screen.getByText("SDT compression")).toBeInTheDocument();
    expect(screen.getByText("Throughput (events/sec)")).toBeInTheDocument();
    expect(screen.getByText("Live event stream")).toBeInTheDocument();
    expect(
      await screen.findByText(/No events in the last 5 minutes/i),
    ).toBeInTheDocument();
  });

  it("uses the latest available e2e latency window", async () => {
    vi.mocked(api.getThroughput)
      .mockReset()
      .mockResolvedValueOnce({
        data: [
          {
            window_start: "2026-03-26T00:00:00Z",
            window_end: "2026-03-26T00:00:05Z",
            records_raw: 100,
            records_after_sdt: 80,
            bytes_estimate: 8000,
            tags_active: 20,
            sdt_compression_ratio: 20,
            sdt_enabled: true,
          },
        ],
        meta,
      })
      .mockResolvedValueOnce({ data: [], meta });

    vi.mocked(api.getLatency).mockResolvedValue({
      data: [
        {
          window_start: "2026-03-26T00:00:00Z",
          window_end: "2026-03-26T00:00:05Z",
          avg_latency_ms: 45,
          p99_latency_ms: 90,
          avg_e2e_latency_ms: 2200,
          p99_e2e_latency_ms: 3400,
          avg_delta_to_app_ms: 850,
          p99_delta_to_app_ms: 1200,
        },
        {
          window_start: "2026-03-26T00:00:05Z",
          window_end: "2026-03-26T00:00:10Z",
          avg_latency_ms: 50,
          p99_latency_ms: 95,
        },
      ],
      meta,
    });

    vi.mocked(api.getEventsLatest).mockResolvedValue({
      data: [
        {
          event_timestamp: "2026-03-26T00:00:09Z",
          ingest_timestamp: "2026-03-26T00:00:09Z",
          asset_id: "site1_asset1",
          asset_type: "battery_bess",
          tag_name: "soc",
          tag_value: 55.2,
          quality: 192,
          sdt_compressed: false,
          compression_ratio: 0,
        },
      ],
      meta,
    });

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(await screen.findByText("2.2s")).toBeInTheDocument();
    expect(screen.getByText("3.4s")).toBeInTheDocument();
    expect(screen.queryByText("Needs CDF commit timestamps")).not.toBeInTheDocument();
  });
});
