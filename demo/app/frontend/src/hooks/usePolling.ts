import { useState, useEffect, useRef, useCallback } from 'react';

interface UsePollingOptions<T> {
  fetcher: () => Promise<T>;
  intervalMs: number;
  enabled?: boolean;
}

interface UsePollingResult<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  /** True when data is from a previous successful fetch and the latest fetch returned empty/null. */
  stale: boolean;
}

/** Returns true if the value looks "empty" — null, undefined, or an empty array. */
function isEmpty(v: unknown): boolean {
  if (v == null) return true;
  if (Array.isArray(v) && v.length === 0) return true;
  return false;
}

export function usePolling<T>({
  fetcher,
  intervalMs,
  enabled = true,
}: UsePollingOptions<T>): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [stale, setStale] = useState(false);
  const fetcherRef = useRef(fetcher);
  const inflightRef = useRef(false);

  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  const doFetch = useCallback(async () => {
    // Skip if a fetch is already in-flight (prevents pile-up when warehouse is slow)
    if (inflightRef.current) return;
    inflightRef.current = true;
    try {
      const result = await fetcherRef.current();
      if (isEmpty(result)) {
        // Keep previous data but mark as stale
        setStale(true);
      } else {
        setData(result);
        setStale(false);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      // Keep previous data on error, mark stale
      setStale(true);
    } finally {
      setLoading(false);
      inflightRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;

    doFetch();
    const id = setInterval(doFetch, intervalMs);
    return () => clearInterval(id);
  }, [doFetch, intervalMs, enabled]);

  return { data, error, loading, stale };
}
