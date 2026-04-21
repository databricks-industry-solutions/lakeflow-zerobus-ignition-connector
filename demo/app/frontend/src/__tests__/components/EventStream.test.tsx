import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import EventStream from '../../components/EventStream';

describe('EventStream', () => {
  it('renders columns: Timestamp, Asset, Tag, Value, Quality, Latency, SDT', () => {
    render(<EventStream events={[]} />);

    expect(screen.getByText('Timestamp')).toBeInTheDocument();
    expect(screen.getByText('Asset')).toBeInTheDocument();
    expect(screen.getByText('Tag')).toBeInTheDocument();
    expect(screen.getByText('Value')).toBeInTheDocument();
    expect(screen.getByText('Quality')).toBeInTheDocument();
    expect(screen.getByText('Latency')).toBeInTheDocument();
    expect(screen.getByText('SDT')).toBeInTheDocument();
  });

  it('renders event rows', () => {
    const events = [
      {
        event_timestamp: '2026-02-12T10:00:00Z',
        ingest_timestamp: '2026-02-12T10:00:02Z',
        asset_id: 'wind_hexham_t01',
        asset_type: 'wind_turbine',
        tag_name: 'generator/power_kw',
        tag_value: 1500.5,
        quality: 192,
        sdt_compressed: true,
        compression_ratio: 6.2,
      },
    ];

    render(<EventStream events={events} />);

    expect(screen.getByText('wind_hexham_t01')).toBeInTheDocument();
    expect(screen.getByText('generator/power_kw')).toBeInTheDocument();
    expect(screen.getByText('Good')).toBeInTheDocument();
  });
});
