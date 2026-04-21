/**
 * Gate test for AC-14: Download CSV button on Asset Detail.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

describe('AC-14: Download CSV button', () => {
  it('renders a CSV download button on Asset Detail page', async () => {
    let AssetDetail: any;
    try {
      const mod = await import('../../pages/AssetDetail');
      AssetDetail = mod.default;
    } catch {
      expect.fail('GATE NOT PASSED: AC-14 — AssetDetail page cannot be imported');
      return;
    }

    render(
      <MemoryRouter initialEntries={['/assets/bess01']}>
        <Routes>
          <Route path="/assets/:assetId" element={<AssetDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    const csvBtn = screen.queryByRole('button', { name: /csv|download|export/i })
      ?? screen.queryByText(/download csv/i)
      ?? screen.queryByText(/export/i);
    expect(csvBtn).toBeTruthy();
  });
});
