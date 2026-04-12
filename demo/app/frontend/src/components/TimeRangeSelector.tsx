import { useState } from "react";

export type PresetKey = "5m" | "15m" | "1h" | "6h" | "24h" | "7d" | "30d" | "Custom";

export interface TimeRange {
  from: string;
  to: string;
  preset?: PresetKey;
}

interface Props {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
}

const PRESETS: { key: PresetKey; label: string; minutes: number }[] = [
  { key: "5m", label: "5m", minutes: 5 },
  { key: "15m", label: "15m", minutes: 15 },
  { key: "1h", label: "1h", minutes: 60 },
  { key: "6h", label: "6h", minutes: 360 },
  { key: "24h", label: "24h", minutes: 1440 },
  { key: "7d", label: "7d", minutes: 10080 },
  { key: "30d", label: "30d", minutes: 43200 },
];

function toLocalInput(iso: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, "0");
    return (
      d.getFullYear() +
      "-" +
      pad(d.getMonth() + 1) +
      "-" +
      pad(d.getDate()) +
      "T" +
      pad(d.getHours()) +
      ":" +
      pad(d.getMinutes())
    );
  } catch {
    return "";
  }
}

function fromLocalInput(local: string): string {
  if (!local) return new Date().toISOString();
  return new Date(local).toISOString();
}

export default function TimeRangeSelector({ value, onChange }: Props) {
  const [customFrom, setCustomFrom] = useState(toLocalInput(value.from));
  const [customTo, setCustomTo] = useState(toLocalInput(value.to));

  function handlePreset(key: PresetKey) {
    const preset = PRESETS.find((p) => p.key === key);
    if (!preset) return;
    const to = new Date();
    const from = new Date(to.getTime() - preset.minutes * 60 * 1000);
    onChange({ from: from.toISOString(), to: to.toISOString(), preset: key });
  }

  function handleCustomApply() {
    const from = fromLocalInput(customFrom);
    const to = fromLocalInput(customTo);
    onChange({ from, to, preset: "Custom" });
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {PRESETS.map((p) => (
        <button
          key={p.key}
          onClick={() => handlePreset(p.key)}
          aria-label={p.label}
          className={`px-3 py-1 rounded text-sm ${
            value.preset === p.key
              ? "bg-databricks-primary text-white"
              : "bg-gray-100 text-gray-600 hover:text-gray-800"
          }`}
        >
          {p.label}
        </button>
      ))}
      <button
        onClick={() => onChange({ ...value, preset: "Custom" })}
        aria-label="Custom"
        className={`px-3 py-1 rounded text-sm ${
          value.preset === "Custom"
            ? "bg-databricks-primary text-white"
            : "bg-gray-100 text-gray-600 hover:text-gray-800"
        }`}
      >
        Custom
      </button>

      {value.preset === "Custom" && (
        <div className="flex items-center gap-2 flex-wrap">
          <label className="text-sm text-gray-600">
            From
            <input
              type="datetime-local"
              aria-label="From date and time"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
              className="ml-1 border border-gray-300 rounded px-2 py-0.5 text-sm"
            />
          </label>
          <label className="text-sm text-gray-600">
            To
            <input
              type="datetime-local"
              aria-label="To date and time"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
              className="ml-1 border border-gray-300 rounded px-2 py-0.5 text-sm"
            />
          </label>
          <button
            onClick={handleCustomApply}
            className="px-3 py-1 bg-databricks-primary text-white rounded text-sm"
          >
            Apply
          </button>
        </div>
      )}
    </div>
  );
}
