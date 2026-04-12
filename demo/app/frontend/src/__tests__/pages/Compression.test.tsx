import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Compression from '../../pages/Compression';

// Mock recharts
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  Bar: () => <div />,
  Line: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Cell: () => <div />,
  Legend: () => <div />,
}));

// Mock API
vi.mock('../../services/api', () => ({
  api: {
    getCompressionComparison: vi.fn().mockRejectedValue(new Error('no server')),
    getSdtConfig: vi.fn().mockRejectedValue(new Error('no server')),
    updateSdtConfig: vi.fn().mockRejectedValue(new Error('no server')),
  },
}));

describe('Compression page', () => {
  it('renders waterfall chart section and SDT tuning panel', () => {
    render(
      <MemoryRouter>
        <Compression />
      </MemoryRouter>,
    );

    expect(screen.getByText('Compression')).toBeInTheDocument();
    // SDT tuning section (rendered by SdtTuningPanel)
    expect(screen.getByText(/SDT tuning/i)).toBeInTheDocument();
  });
});
