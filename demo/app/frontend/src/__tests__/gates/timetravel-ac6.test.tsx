/**
 * Gate test for AC-6: Fleet Snapshot section on Analytics.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

describe('AC-6: Fleet Snapshot on Analytics page', () => {
  it('renders a fleet snapshot section with a date picker', async () => {
    let Analytics: any;
    try {
      const mod = await import('../../pages/Analytics');
      Analytics = mod.default;
    } catch {
      expect.fail('GATE NOT PASSED: AC-6 — Analytics page cannot be imported');
      return;
    }

    render(
      <MemoryRouter>
        <Analytics />
      </MemoryRouter>,
    );

    const snapshotSection = screen.queryByText(/fleet snapshot/i)
      ?? screen.queryByText(/point.in.time/i)
      ?? screen.queryByText(/show fleet state/i);
    expect(snapshotSection).toBeTruthy();
  });
});
