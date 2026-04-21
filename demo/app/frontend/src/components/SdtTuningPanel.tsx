import { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

interface SdtTuningPanelProps {
  compDevPercent: number;
  compMaxSeconds: number;
  onApply: (config: { comp_dev_percent: number; comp_max_seconds: number }) => void;
}

export default function SdtTuningPanel({
  compDevPercent,
  compMaxSeconds,
  onApply,
}: SdtTuningPanelProps) {
  const [devPercent, setDevPercent] = useState(compDevPercent);
  const [maxSeconds, setMaxSeconds] = useState(compMaxSeconds);

  // Generate sample trend data to visualize compression effect
  const samplePoints = Array.from({ length: 30 }, (_, i) => ({
    t: i,
    raw: Math.sin(i * 0.3) * 50 + 100 + (Math.random() - 0.5) * 10,
  }));

  // Simulate compressed points - higher CompDev = fewer points kept
  const compressedPoints = samplePoints.filter((_, i) => {
    const keepRatio = Math.max(0.1, 1 - devPercent / 6);
    return i === 0 || i === samplePoints.length - 1 || Math.random() < keepRatio;
  });

  const chartData = samplePoints.map((p) => {
    const compressed = compressedPoints.find((cp) => cp.t === p.t);
    return {
      t: p.t,
      raw: p.raw,
      compressed: compressed ? compressed.raw : undefined,
    };
  });

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">SDT tuning</h3>

      {/* CompDev tooltip/explanation */}
      <div className="mb-4 p-2 bg-gray-100 border border-gray-200 rounded text-xs text-gray-600">
        <strong>CompDev = Compression Deviation.</strong> This is the maximum allowed deviation
        from a linear interpolation between archived points. Common CompDev parameter in historian platforms.
      </div>

      {/* Sliders */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label htmlFor="comp-dev-slider" className="block text-sm text-gray-600 mb-1">
            CompDev % ({devPercent.toFixed(1)}%)
          </label>
          <input
            id="comp-dev-slider"
            type="range"
            min="0.1"
            max="5"
            step="0.1"
            value={devPercent}
            onChange={(e) => setDevPercent(parseFloat(e.target.value))}
            className="w-full"
          />
        </div>
        <div>
          <label htmlFor="comp-max-slider" className="block text-sm text-gray-600 mb-1">
            CompMax ({maxSeconds}s)
          </label>
          <input
            id="comp-max-slider"
            type="range"
            min="60"
            max="3600"
            step="60"
            value={maxSeconds}
            onChange={(e) => setMaxSeconds(parseInt(e.target.value, 10))}
            className="w-full"
          />
        </div>
      </div>

      {/* Apply button */}
      <button
        onClick={() => onApply({ comp_dev_percent: devPercent, comp_max_seconds: maxSeconds })}
        className="mb-4 px-4 py-2 bg-databricks-primary text-white rounded hover:bg-databricks-primary/90 text-sm font-medium"
      >
        Apply
      </button>

      {/* Mini trend chart */}
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="t" stroke="#9CA3AF" fontSize={12} />
          <YAxis stroke="#9CA3AF" fontSize={12} />
          <Tooltip
            contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e5e7eb' }}
            labelStyle={{ color: '#374151' }}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="raw"
            name="Raw"
            stroke="#6B7280"
            dot={false}
            strokeWidth={1}
          />
          <Line
            type="monotone"
            dataKey="compressed"
            name="Compressed"
            stroke="#10B981"
            strokeWidth={2}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
