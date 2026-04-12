/**
 * Gate test for AC-2: 24h preset available.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

describe('AC-2: 24h time range preset exists', () => {
  it('renders a 24h option in the time range selector', async () => {
    let AssetDetail: any;
    try {
      const mod = await import('../../pages/AssetDetail');
      AssetDetail = mod.default;
    } catch {
      expect.fail('GATE NOT PASSED: AC-2 — AssetDetail page cannot be imported');
      return;
    }

    render(
      <MemoryRouter initialEntries={['/assets/bess01']}>
        <Routes>
          <Route path="/assets/:assetId" element={<AssetDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    const btn24h = screen.queryByRole('button', { name: /24h/i })
      ?? screen.queryByText(/24h/i);
    expect(btn24h).toBeTruthy();
  });
});
