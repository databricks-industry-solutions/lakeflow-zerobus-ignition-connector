import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { usePolling } from '../../hooks/usePolling';

describe('usePolling', () => {
  it('calls fetch at specified interval and returns latest data', async () => {
    let callCount = 0;
    const fetcher = vi.fn(async () => {
      callCount++;
      return { value: callCount };
    });

    const { result } = renderHook(() =>
      usePolling({ fetcher, intervalMs: 100 }),
    );

    // Wait for initial fetch
    await waitFor(() => {
      expect(result.current.data).toEqual({ value: 1 });
    });
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();

    // Wait for at least one more interval
    await act(async () => {
      await new Promise((r) => setTimeout(r, 150));
    });

    await waitFor(() => {
      expect(fetcher.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
  });

  it('sets error when fetcher fails', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() =>
      usePolling({ fetcher, intervalMs: 5000 }),
    );

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe('Network error');
    });
  });

  it('does not fetch when disabled', async () => {
    const fetcher = vi.fn().mockResolvedValue({ value: 1 });

    renderHook(() =>
      usePolling({ fetcher, intervalMs: 100, enabled: false }),
    );

    // Wait and verify no calls
    await act(async () => {
      await new Promise((r) => setTimeout(r, 250));
    });

    expect(fetcher).not.toHaveBeenCalled();
  });
});
