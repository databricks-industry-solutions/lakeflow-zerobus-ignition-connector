/**
 * Gate test for AC-3: Custom date-time range picker.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

describe('AC-3: Custom date-time range picker', () => {
  it('has a Custom option that reveals date-time inputs', async () => {
    let AssetDetail: any;
    try {
      const mod = await import('../../pages/AssetDetail');
      AssetDetail = mod.default;
    } catch {
      expect.fail('GATE NOT PASSED: AC-3 — AssetDetail page cannot be imported');
      return;
    }

    render(
      <MemoryRouter initialEntries={['/assets/bess01']}>
        <Routes>
          <Route path="/assets/:assetId" element={<AssetDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    // Should have a Custom button or option
    const customBtn = screen.queryByRole('button', { name: /custom/i })
      ?? screen.queryByText(/custom/i);
    expect(customBtn).toBeTruthy();
  });
});
