export function formatNumber(value: number | string | null | undefined, decimals = 2): string {
  if (value == null) return '-';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '-';
  return num.toLocaleString('en-AU', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function qualityLabel(quality: number | string | null | undefined): string {
  const q = typeof quality === 'string' ? parseInt(quality, 10) : quality;
  if (q == null || isNaN(q)) return 'Unknown';
  if (q >= 192) return 'Good';
  if (q >= 64) return 'Uncertain';
  return 'Bad';
}

export function formatLatency(ms: number | string | null | undefined): string {
  if (ms == null) return '-';
  const v = typeof ms === 'string' ? parseFloat(ms) : ms;
  if (isNaN(v)) return '-';
  if (v >= 1000) return `${(v / 1000).toFixed(1)}s`;
  return `${Math.round(v)}ms`;
}

export function latencyColor(ms: number | string | null | undefined): string {
  const v = typeof ms === 'string' ? parseFloat(ms) : ms;
  if (v == null || isNaN(v)) return 'text-gray-600';
  if (v < 5000) return 'text-brand-green';
  if (v < 10000) return 'text-brand-amber';
  return 'text-brand-red';
}

export function formatTimestamp(ts: string): string {
  return new Date(ts).toLocaleTimeString('en-AU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}
