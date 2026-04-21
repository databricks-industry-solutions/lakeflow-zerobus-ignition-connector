import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import BigNumberCard from '../../components/BigNumberCard';

describe('BigNumberCard', () => {
  it('displays value and label', () => {
    render(<BigNumberCard label="Active tags" value="1,250" />);

    expect(screen.getByText('Active tags')).toBeInTheDocument();
    expect(screen.getByText('1,250')).toBeInTheDocument();
  });

  it('applies color class based on threshold', () => {
    const { container } = render(
      <BigNumberCard label="Latency" value="3,200ms" colorClass="text-brand-green" />,
    );

    const valueEl = container.querySelector('.text-brand-green');
    expect(valueEl).toBeInTheDocument();
    expect(valueEl?.textContent).toBe('3,200ms');
  });

  it('uses default color class when none provided', () => {
    const { container } = render(
      <BigNumberCard label="Tags" value="50" />,
    );

    const valueEl = container.querySelector('.text-databricks-primary');
    expect(valueEl).toBeInTheDocument();
  });

  it('shows subtitle when provided', () => {
    render(
      <BigNumberCard label="Tags" value="50" subtitle="Projected: 2M" />,
    );

    expect(screen.getByText('Projected: 2M')).toBeInTheDocument();
  });
});
