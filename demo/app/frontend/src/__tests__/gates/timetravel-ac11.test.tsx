/**
 * Gate test for AC-11: Investigate button on health scores table.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

describe('AC-11: Investigate button on health scores', () => {
  it('has Investigate buttons on Analytics page', async () => {
    let Analytics: any;
    try {
      const mod = await import('../../pages/Analytics');
      Analytics = mod.default;
    } catch {
      expect.fail('GATE NOT PASSED: AC-11 — Analytics page cannot be imported');
      return;
    }

    render(
      <MemoryRouter>
        <Analytics />
      </MemoryRouter>,
    );

    // Look for an investigate button or link
    const investigateBtn = screen.queryByText(/investigate/i)
      ?? screen.queryByRole('link', { name: /investigate/i });
    // This may not be visible without data, so check for the element existence
    // in a more lenient way — at minimum the component should have the concept
    expect(investigateBtn).toBeTruthy();
  });
});
