import { useState, useCallback } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import AssetCard from '../components/AssetCard';

type AssetFilter = 'all' | 'wind_turbine' | 'battery_bess';

export default function Assets() {
  const [filter, setFilter] = useState<AssetFilter>('all');

  const assetsFetcher = useCallback(
    () => api.getAssets().then((r) => r.data),
    [],
  );

  const { data: assets } = usePolling({
    fetcher: assetsFetcher,
    intervalMs: 5000,
  });

  const filtered = (assets ?? []).filter(
    (a) => filter === 'all' || a.asset_type === filter,
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-heading text-2xl font-semibold text-gray-900">Assets</h2>
        <div className="flex gap-2">
          {(['all', 'wind_turbine', 'battery_bess'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded text-sm ${
                filter === f
                  ? 'bg-databricks-primary text-white'
                  : 'bg-gray-100 text-gray-600 hover:text-gray-800'
              }`}
            >
              {f === 'all' ? 'All' : f === 'wind_turbine' ? 'Wind' : 'Battery'}
            </button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filtered.map((asset) => (
          <AssetCard key={asset.asset_id} asset={asset} />
        ))}
      </div>
    </div>
  );
}
