/**
 * Gate test for AC-9: Compare mode toggle.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

describe('AC-9: Compare toggle on Fleet Snapshot', () => {
  it('has a compare toggle element', async () => {
    let Analytics: any;
    try {
      const mod = await import('../../pages/Analytics');
      Analytics = mod.default;
    } catch {
      expect.fail('GATE NOT PASSED: AC-9 — Analytics page cannot be imported');
      return;
    }

    render(
      <MemoryRouter>
        <Analytics />
      </MemoryRouter>,
    );

    const compareToggle = screen.queryByText(/compare/i)
      ?? screen.queryByRole('checkbox', { name: /compare/i })
      ?? screen.queryByRole('switch', { name: /compare/i });
    expect(compareToggle).toBeTruthy();
  });
});
