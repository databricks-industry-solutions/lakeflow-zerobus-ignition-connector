import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Architecture from '../../pages/Architecture';

describe('Architecture page', () => {
  it('renders before/after diagrams and comparison table', () => {
    render(
      <MemoryRouter>
        <Architecture />
      </MemoryRouter>,
    );

    expect(screen.getByText('Architecture')).toBeInTheDocument();
    // Before/After sections
    expect(screen.getByText(/before/i)).toBeInTheDocument();
    expect(screen.getByText(/after/i)).toBeInTheDocument();
    // Comparison table dimensions
    expect(screen.getByText('Components')).toBeInTheDocument();
    expect(screen.getByText('Licensing')).toBeInTheDocument();
  });
});
