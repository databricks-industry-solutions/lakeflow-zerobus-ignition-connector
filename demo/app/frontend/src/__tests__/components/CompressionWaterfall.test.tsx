import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import CompressionWaterfall from '../../components/CompressionWaterfall';

// Mock recharts
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Cell: () => <div />,
  Legend: () => <div />,
}));

const mockLayers = [
  { layer_name: 'raw', event_count: 10000, size_bytes: 5000000, ratio_vs_raw: 1.0 },
  { layer_name: 'after_sdt', event_count: 1600, size_bytes: 800000, ratio_vs_raw: 6.25 },
  { layer_name: 'after_delta', event_count: 1600, size_bytes: 120000, ratio_vs_raw: 41.67 },
  { layer_name: 'combined', event_count: 1600, size_bytes: 120000, ratio_vs_raw: 41.67 },
];

describe('CompressionWaterfall', () => {
  it('renders 3 visible layers with labels', () => {
    render(<CompressionWaterfall layers={mockLayers} />);

    expect(screen.getAllByText('Raw (uncompressed)').length).toBeGreaterThan(0);
    expect(screen.getAllByText('After SDT').length).toBeGreaterThan(0);
    expect(screen.getAllByText('On disk (Delta + ZSTD)').length).toBeGreaterThan(0);
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });

  it('includes the compression callout text', () => {
    render(<CompressionWaterfall layers={mockLayers} />);

    expect(
      screen.getByText(/Other platforms apply Swinging Door compression/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/same algorithm/i),
    ).toBeInTheDocument();
  });
});
