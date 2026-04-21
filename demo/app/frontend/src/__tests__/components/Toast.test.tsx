import { describe, it, expect, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import Toast from '../../components/Toast';

describe('Toast', () => {
  it('displays error message', () => {
    render(<Toast message="Network error occurred" onClose={vi.fn()} />);

    expect(screen.getByText('Network error occurred')).toBeInTheDocument();
  });

  it('auto-dismisses after timeout', () => {
    vi.useFakeTimers();
    const onClose = vi.fn();

    render(<Toast message="Error" onClose={onClose} autoCloseMs={3000} />);

    expect(onClose).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(onClose).toHaveBeenCalled();
    vi.useRealTimers();
  });
});
