/**
 * Gate test for AC-10: Show SQL collapsible.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

describe('AC-10: Show SQL collapsible on Fleet Snapshot', () => {
  it('has a Show SQL element on Analytics page', async () => {
    let Analytics: any;
    try {
      const mod = await import('../../pages/Analytics');
      Analytics = mod.default;
    } catch {
      expect.fail('GATE NOT PASSED: AC-10 — Analytics page cannot be imported');
      return;
    }

    render(
      <MemoryRouter>
        <Analytics />
      </MemoryRouter>,
    );

    const showSql = screen.queryByText(/show sql/i)
      ?? screen.queryByText(/view query/i);
    expect(showSql).toBeTruthy();
  });
});
