import { useNavigate } from 'react-router-dom';
import type { Asset } from '../services/api';
import { formatNumber } from '../utils/format';

interface AssetCardProps {
  asset: Asset;
}

function statusFromAlarmCode(code?: number | string): { label: string; color: string } {
  if (code === undefined || code === null || code === 0 || code === 'OK')
    return { label: 'OK', color: 'text-brand-green' };
  if (typeof code === 'string') {
    if (code === 'CRITICAL') return { label: 'Alarm', color: 'text-brand-red' };
    return { label: 'Warning', color: 'text-brand-amber' };
  }
  if (code < 100) return { label: 'Warning', color: 'text-brand-amber' };
  return { label: 'Alarm', color: 'text-brand-red' };
}

function typeIcon(type: string): string {
  return type === 'wind_turbine' ? '\u{1F32C}\uFE0F' : '\u{1F50B}';
}

export default function AssetCard({ asset }: AssetCardProps) {
  const navigate = useNavigate();
  const status = statusFromAlarmCode(asset.alarm_code);

  return (
    <button
      onClick={() => navigate(`/assets/${asset.asset_id}`)}
      className="bg-surface-card border border-gray-200 rounded-card p-4 text-left shadow-card
                 hover:border-databricks-primary/50 hover:shadow-card-hover transition-all duration-200 w-full
                 focus:outline-none focus-visible:ring-2 focus-visible:ring-databricks-primary focus-visible:ring-offset-2"
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl">{typeIcon(asset.asset_type)}</span>
        <h3 className="font-heading font-semibold text-gray-900">{asset.asset_name}</h3>
      </div>
      <div className="space-y-1 text-sm">
        <p className="text-gray-600">
          {asset.site_name} &middot; {asset.tag_count} tags
        </p>
        <p>
          Status: <span className={status.color}>{status.label}</span>
        </p>
        {asset.compression_ratio != null && asset.compression_ratio > 0 && (
          <p className="text-gray-600">
            Compression: {formatNumber(asset.compression_ratio, 1)}:1
          </p>
        )}
        {asset.last_update && (
          <p className="text-gray-500 text-xs">
            Last update: {new Date(asset.last_update).toLocaleTimeString()}
          </p>
        )}
      </div>
    </button>
  );
}
