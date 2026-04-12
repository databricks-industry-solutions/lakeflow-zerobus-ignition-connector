import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ThroughputChart from "../../components/ThroughputChart";

// Mock recharts
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  AreaChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="area-chart">{children}</div>
  ),
  Area: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
}));

describe("ThroughputChart", () => {
  it("renders with mock data without crashing", () => {
    const mockData = [
      {
        window_start: "2026-02-12T10:00:00Z",
        window_end: "2026-02-12T10:00:05Z",
        records_raw: 150,
        records_after_sdt: 25,
        bytes_estimate: 12000,
        tags_active: 50,
        sdt_compression_ratio: 6.0,
      },
      {
        window_start: "2026-02-12T10:00:05Z",
        window_end: "2026-02-12T10:00:10Z",
        records_raw: 160,
        records_after_sdt: 28,
        bytes_estimate: 13000,
        tags_active: 50,
        sdt_compression_ratio: 5.7,
      },
    ];

    render(
      <ThroughputChart rawTagsData={mockData} rawThroughputData={mockData} />,
    );

    expect(screen.getByText("Throughput (events/sec)")).toBeInTheDocument();
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("renders with empty data", () => {
    render(<ThroughputChart rawTagsData={[]} rawThroughputData={[]} />);
    expect(screen.getByText("Throughput (events/sec)")).toBeInTheDocument();
  });
});
