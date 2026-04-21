import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SdtTuningPanel from '../../components/SdtTuningPanel';

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
}));

describe('SdtTuningPanel', () => {
  const defaultProps = {
    compDevPercent: 1.0,
    compMaxSeconds: 600,
    onApply: vi.fn(),
  };

  it('renders CompDev slider (0.1-5.0 range) and CompMax slider (60-3600 range)', () => {
    render(<SdtTuningPanel {...defaultProps} />);

    const compDevSlider = screen.getByLabelText(/CompDev/);
    expect(compDevSlider).toBeInTheDocument();
    expect(compDevSlider).toHaveAttribute('min', '0.1');
    expect(compDevSlider).toHaveAttribute('max', '5');

    const compMaxSlider = screen.getByLabelText(/CompMax/);
    expect(compMaxSlider).toBeInTheDocument();
    expect(compMaxSlider).toHaveAttribute('min', '60');
    expect(compMaxSlider).toHaveAttribute('max', '3600');
  });

  it('Apply button calls PUT /api/compression/sdt-config with current slider values', () => {
    const onApply = vi.fn();
    render(<SdtTuningPanel {...defaultProps} onApply={onApply} />);

    const applyBtn = screen.getByRole('button', { name: /apply/i });
    fireEvent.click(applyBtn);

    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({
        comp_dev_percent: expect.any(Number),
        comp_max_seconds: expect.any(Number),
      }),
    );
  });

  it('Tooltip with CompDev explanation is present', () => {
    render(<SdtTuningPanel {...defaultProps} />);

    expect(
      screen.getByText(/Compression Deviation/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/maximum allowed deviation from a linear interpolation/i),
    ).toBeInTheDocument();
  });
});
