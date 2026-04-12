import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

export interface CompressionLayer {
  layer_name: string;
  event_count: number;
  size_bytes: number;
  ratio_vs_raw: number;
}

interface CompressionWaterfallProps {
  layers: CompressionLayer[];
}

/** Only show these three layers, in order. "combined" is dropped since it
 *  duplicates "after_delta" — both represent the same on-disk size. */
const VISIBLE_LAYERS = ['raw', 'after_sdt', 'after_delta'];

const LAYER_META: Record<string, { label: string; color: string; description: string }> = {
  raw: {
    label: 'Raw (uncompressed)',
    color: '#6B7280',
    description: 'Estimated size before any compression — every tag-change event at ~150 bytes/row.',
  },
  after_sdt: {
    label: 'After SDT',
    color: '#3B82F6',
    description: 'After Swinging Door Trending at the connector — redundant points within the deviation band are filtered out before data leaves the gateway.',
  },
  after_delta: {
    label: 'On disk (Delta + ZSTD)',
    color: '#10B981',
    description: 'Final on-disk size in Delta Lake with ZSTD columnar compression — this is what you actually store and pay for.',
  },
};

function formatBytes(bytes: number): string {
  const n = Number(bytes);
  if (n === 0 || !Number.isFinite(n)) return '0 B';
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)} GB`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)} MB`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(2)} KB`;
  return `${Math.round(n)} B`;
}

function formatRatio(ratio: number): string {
  if (ratio <= 1) return '1:1';
  return `${ratio.toFixed(1)}:1`;
}

export default function CompressionWaterfall({ layers }: CompressionWaterfallProps) {
  // Filter to the three meaningful layers
  const visibleLayers = VISIBLE_LAYERS
    .map((name) => layers.find((l) => l.layer_name === name))
    .filter((l): l is CompressionLayer => l != null);

  const chartData = visibleLayers.map((l) => {
    const meta = LAYER_META[l.layer_name];
    return {
      name: meta?.label ?? l.layer_name,
      layer_name: l.layer_name,
      size_bytes: l.size_bytes,
      event_count: l.event_count,
      ratio: l.ratio_vs_raw,
      color: meta?.color ?? '#9CA3AF',
      description: meta?.description ?? '',
    };
  });

  const rawLayer = visibleLayers.find((l) => l.layer_name === 'raw');
  const deltaLayer = visibleLayers.find((l) => l.layer_name === 'after_delta');

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-1">
        Compression waterfall
      </h3>
      <p className="text-xs text-gray-500 mb-4">
        Each bar shows the data volume at a different stage of the pipeline. SDT reduces row count at the connector; Delta + ZSTD compresses what remains on disk.
      </p>

      {/* One-line summary: Incoming → On disk */}
      {rawLayer != null && deltaLayer != null && (
        <p className="text-xs text-gray-600 mb-3">
          Incoming: {rawLayer.event_count.toLocaleString()} rows, {formatBytes(rawLayer.size_bytes)} (est.) → On
          disk: {formatBytes(deltaLayer.size_bytes)} (Delta + ZSTD) ={' '}
          <strong className="text-brand-green">{formatRatio(deltaLayer.ratio_vs_raw)} total reduction</strong>.
        </p>
      )}

      {/* Legend */}
      <div className="flex gap-4 mb-4 text-xs text-gray-600">
        {chartData.map((d) => (
          <span key={d.layer_name} className="flex items-center gap-1">
            <span
              className="inline-block w-3 h-3 rounded"
              style={{ backgroundColor: d.color }}
            />
            {d.name}
          </span>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="name" stroke="#9CA3AF" fontSize={12} />
          <YAxis stroke="#9CA3AF" fontSize={12} tickFormatter={(v: number) => formatBytes(v)} />
          <Tooltip
            contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e5e7eb' }}
            labelStyle={{ color: '#374151' }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload;
              return (
                <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm shadow-lg max-w-xs">
                  <div className="font-medium text-gray-800 mb-1">{d.name}</div>
                  <div className="text-xs text-gray-500 mb-2">{d.description}</div>
                  <div className="text-gray-600">Rows: {d.event_count?.toLocaleString() ?? '—'}</div>
                  <div className="text-gray-600">Size: {formatBytes(d.size_bytes ?? 0)}</div>
                  {d.ratio != null && d.ratio > 1 && (
                    <div className="text-brand-green font-medium">{formatRatio(d.ratio)} vs raw</div>
                  )}
                </div>
              );
            }}
          />
          <Bar dataKey="size_bytes" name="Size" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, index) => (
              <Cell key={index} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Step-by-step explanation */}
      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        {chartData.map((d, i) => (
          <div key={d.layer_name} className="flex items-start gap-2 text-xs">
            <span className="font-bold text-gray-400 mt-0.5">{i + 1}.</span>
            <div>
              <span className="font-semibold" style={{ color: d.color }}>{d.name}</span>
              <p className="text-gray-500 leading-relaxed mt-0.5">{d.description}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Callout */}
      <div className="mt-4 p-3 bg-gray-100 border border-gray-200 rounded text-sm text-gray-700">
        Other platforms apply Swinging Door compression at the archive. We apply the{' '}
        <strong className="text-databricks-primary">same algorithm</strong> at the connector
        — plus Delta columnar encoding on top. Same compression, open format, fewer moving parts.
      </div>
    </div>
  );
}
