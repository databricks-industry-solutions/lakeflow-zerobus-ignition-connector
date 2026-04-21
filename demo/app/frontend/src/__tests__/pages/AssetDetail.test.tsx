import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AssetDetail from '../../pages/AssetDetail';

// Mock recharts
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  Line: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
  ReferenceLine: () => <div />,
}));

vi.mock('../../services/api', () => ({
  api: {
    getAsset: vi.fn().mockResolvedValue({
      data: {
        asset_id: 'wind_hexham_t01',
        asset_name: 'Hexham Turbine 01',
        asset_type: 'wind_turbine',
        site_name: 'Hexham',
        capacity_mw: 3.6,
        tag_count: 13,
      },
    }),
    getAssetTags: vi.fn().mockResolvedValue({ data: [] }),
    exportAssetTagsCsv: vi.fn().mockResolvedValue(undefined),
    getForensics: vi.fn().mockResolvedValue({ data: [] }),
  },
}));

describe('AssetDetail page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders metadata header, trend charts, and tag table', async () => {
    render(
      <MemoryRouter initialEntries={['/assets/wind_hexham_t01']}>
        <Routes>
          <Route path="/assets/:id" element={<AssetDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    // Time range controls are always present (TimeRangeSelector presets)
    expect(screen.getByText('5m')).toBeInTheDocument();
    expect(screen.getByText('15m')).toBeInTheDocument();
    expect(screen.getByText('1h')).toBeInTheDocument();

    // Raw vs compressed toggle
    expect(screen.getByText('Show raw vs compressed')).toBeInTheDocument();

    // Wait for async data to load
    await waitFor(() => {
      expect(screen.getByText('All tags')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText('generator/power_kw')).toBeInTheDocument();
      expect(screen.getByText('rotor/wind_speed_ms')).toBeInTheDocument();
    });
  });
});
