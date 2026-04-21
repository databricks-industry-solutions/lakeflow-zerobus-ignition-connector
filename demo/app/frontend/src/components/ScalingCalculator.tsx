import { useState } from 'react';

const STREAM_LIMIT = 15_000;

interface Preset {
  label: string;
  totalTags: number;
  scanRate: number;
  compression: number;
}

const presets: Preset[] = [
  { label: 'Small site (50K tags)', totalTags: 50_000, scanRate: 1, compression: 6 },
  { label: 'Medium (500K)', totalTags: 500_000, scanRate: 1, compression: 6 },
  { label: 'Large fleet (2M+)', totalTags: 2_000_000, scanRate: 1, compression: 6 },
];

function fmtK(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

export default function ScalingCalculator() {
  const [totalTags, setTotalTags] = useState(1_000_000);
  const [scanRate, setScanRate] = useState(1);
  const [compression, setCompression] = useState(6);

  const effectivePerStream = STREAM_LIMIT * compression;
  const rawRate = totalTags / scanRate;
  const streamsNeeded = Math.max(1, Math.ceil(rawRate / effectivePerStream));

  function applyPreset(p: Preset) {
    setTotalTags(p.totalTags);
    setScanRate(p.scanRate);
    setCompression(p.compression);
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">
        Scaling calculator
      </h3>

      {/* Presets */}
      <div className="flex flex-wrap gap-2 mb-5">
        {presets.map((p) => (
          <button
            key={p.label}
            onClick={() => applyPreset(p)}
            className="px-3 py-1 text-xs rounded border border-gray-200 text-gray-700 hover:bg-gray-100 hover:text-databricks-primary transition-colors"
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Sliders */}
      <div className="space-y-4 mb-5">
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">Total tags</span>
            <span className="text-gray-800 font-medium">{fmtK(totalTags)}</span>
          </div>
          <input
            type="range"
            min={1_000}
            max={5_000_000}
            step={10_000}
            value={totalTags}
            onChange={(e) => setTotalTags(Number(e.target.value))}
            className="w-full accent-databricks-primary"
          />
        </div>

        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">Scan rate</span>
            <span className="text-gray-800 font-medium">{scanRate}s</span>
          </div>
          <input
            type="range"
            min={1}
            max={60}
            step={1}
            value={scanRate}
            onChange={(e) => setScanRate(Number(e.target.value))}
            className="w-full accent-databricks-primary"
          />
        </div>

        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">Compression ratio</span>
            <span className="text-gray-800 font-medium">{compression}:1</span>
          </div>
          <input
            type="range"
            min={2}
            max={15}
            step={1}
            value={compression}
            onChange={(e) => setCompression(Number(e.target.value))}
            className="w-full accent-databricks-primary"
          />
        </div>
      </div>

      {/* Results */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-surface-card border border-gray-200 rounded-lg p-3 shadow-card">
          <p className="text-xs text-gray-500 mb-1">Effective throughput / stream</p>
          <p className="text-xl font-bold text-databricks-primary">
            {fmtK(effectivePerStream)} rows/s
          </p>
        </div>
        <div className="bg-surface-card border border-gray-200 rounded-lg p-3 shadow-card">
          <p className="text-xs text-gray-500 mb-1">Streams needed</p>
          <p className="text-xl font-bold text-brand-green">
            {streamsNeeded}
          </p>
        </div>
      </div>
    </div>
  );
}
