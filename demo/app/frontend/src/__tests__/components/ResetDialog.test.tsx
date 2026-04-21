import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockResetDemo = vi.fn();

vi.mock('../../services/api', () => ({
  api: {
    resetDemo: (...args: unknown[]) => mockResetDemo(...args),
  },
}));

import ResetDialog from '../../components/ResetDialog';

describe('ResetDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockResetDemo.mockResolvedValue({ data: { status: 'reset_complete' }, meta: { timestamp: '', query_time_ms: 0 } });
  });

  it('reset button opens confirmation dialog', () => {
    render(<ResetDialog />);

    const resetButton = screen.getByRole('button', { name: /reset/i });
    fireEvent.click(resetButton);

    expect(screen.getByText(/Are you sure/i)).toBeInTheDocument();
  });

  it('confirming reset calls POST /api/admin/reset', async () => {
    render(<ResetDialog />);

    fireEvent.click(screen.getByRole('button', { name: /reset/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(mockResetDemo).toHaveBeenCalled();
    });
  });

  it('cancel closes dialog without calling API', () => {
    render(<ResetDialog />);

    fireEvent.click(screen.getByRole('button', { name: /reset/i }));
    expect(screen.getByText(/Are you sure/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(screen.queryByText(/Are you sure/i)).not.toBeInTheDocument();
    expect(mockResetDemo).not.toHaveBeenCalled();
  });
});
