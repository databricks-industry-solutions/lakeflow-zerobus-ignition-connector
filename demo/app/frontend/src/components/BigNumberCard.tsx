interface BigNumberCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  colorClass?: string;
  /** When set, shows a left accent border in the semantic color (good / warning / bad). */
  accent?: 'success' | 'warning' | 'error';
  /** When set, renders a thin progress bar under the big number. */
  progress?: { value: number; max: number };
}

const accentBorderClass: Record<NonNullable<BigNumberCardProps['accent']>, string> = {
  success: 'border-l-4 border-l-semantic-success',
  warning: 'border-l-4 border-l-semantic-warning',
  error: 'border-l-4 border-l-semantic-error',
};

export default function BigNumberCard({
  label,
  value,
  subtitle,
  colorClass = 'text-databricks-primary',
  accent,
  progress,
}: BigNumberCardProps) {
  const pct = progress ? Math.min((progress.value / progress.max) * 100, 100) : 0;

  return (
    <div
      className={`bg-surface-card border border-gray-200 rounded-card p-4 shadow-card transition-shadow duration-200 ${
        accent ? accentBorderClass[accent] : ''
      }`}
    >
      <p className="text-sm text-gray-600 mb-1">{label}</p>
      <p className={`text-4xl font-bold tabular-nums ${colorClass}`}>{value}</p>
      {progress && (
        <div className="mt-2 h-1.5 w-full rounded-full bg-gray-200">
          <div
            className="h-1.5 rounded-full bg-databricks-primary transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
      {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
    </div>
  );
}
