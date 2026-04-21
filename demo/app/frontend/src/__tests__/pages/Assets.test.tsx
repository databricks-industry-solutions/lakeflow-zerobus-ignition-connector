import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Assets from '../../pages/Assets';

vi.mock('../../services/api', () => ({
  api: {
    getAssets: vi.fn().mockRejectedValue(new Error('no server')),
  },
}));

describe('Assets page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders asset grid with filter controls', () => {
    render(
      <MemoryRouter>
        <Assets />
      </MemoryRouter>,
    );

    expect(screen.getByText('Assets')).toBeInTheDocument();

    // Filter buttons
    expect(screen.getByText('All')).toBeInTheDocument();
    expect(screen.getByText('Wind')).toBeInTheDocument();
    expect(screen.getByText('Battery')).toBeInTheDocument();
  });
});
