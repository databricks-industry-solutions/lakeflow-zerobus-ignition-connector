import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AssetCard from '../../components/AssetCard';

describe('AssetCard', () => {
  const mockAsset = {
    asset_id: 'wind_hexham_t01',
    asset_name: 'Hexham Turbine 01',
    asset_type: 'wind_turbine',
    site_name: 'Hexham',
    capacity_mw: 3.6,
    tag_count: 13,
    alarm_code: 0,
    compression_ratio: 6.2,
    last_update: '2026-02-12T10:00:00Z',
  };

  it('shows name, type, status, and is clickable', () => {
    render(
      <MemoryRouter>
        <AssetCard asset={mockAsset} />
      </MemoryRouter>,
    );

    expect(screen.getByText('Hexham Turbine 01')).toBeInTheDocument();
    expect(screen.getAllByText(/Hexham/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('OK')).toBeInTheDocument();

    // AssetCard renders as a button (clickable)
    const button = screen.getByRole('button');
    expect(button).toBeInTheDocument();
  });

  it('shows Warning status for non-zero alarm code', () => {
    render(
      <MemoryRouter>
        <AssetCard asset={{ ...mockAsset, alarm_code: 50 }} />
      </MemoryRouter>,
    );

    expect(screen.getByText('Warning')).toBeInTheDocument();
  });

  it('shows Alarm status for high alarm code', () => {
    render(
      <MemoryRouter>
        <AssetCard asset={{ ...mockAsset, alarm_code: 200 }} />
      </MemoryRouter>,
    );

    expect(screen.getByText('Alarm')).toBeInTheDocument();
  });
});
