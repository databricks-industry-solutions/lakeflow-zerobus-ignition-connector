import { useCallback } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import type { NemSnapshotRow, BomCurrentRow } from '../services/api';
import { formatNumber } from '../utils/format';

function priceColor(rrp: number): string {
  if (rrp >= 300) return 'text-brand-red';
  if (rrp >= 100) return 'text-brand-amber';
  return 'text-brand-green';
}

export default function MarketWeather() {
  const nemFetcher = useCallback(
    () => api.marketWeather.getNemSnapshot().then((r) => r.data),
    [],
  );
  const bomFetcher = useCallback(
    () => api.marketWeather.getBomCurrent().then((r) => r.data),
    [],
  );

  const { data: nemSnapshot } = usePolling<NemSnapshotRow[] | undefined>({
    fetcher: nemFetcher,
    intervalMs: 15000,
  });
  const { data: bomCurrent } = usePolling<BomCurrentRow[] | undefined>({
    fetcher: bomFetcher,
    intervalMs: 30000,
  });

  return (
    <div>
      <h2 className="font-heading text-2xl font-semibold text-gray-900 mb-2">
        NEM market & BOM weather
      </h2>
      <p className="text-gray-600 mb-6 max-w-2xl">
        Live data from AEMO NEMWEB (5-min dispatch prices) and Bureau of
        Meteorology (half-hourly observations) — ingested via Lakeflow
        Declarative Pipelines.
      </p>

      {/* NEM Market Snapshot */}
      <section className="mb-8">
        <h3 className="font-heading text-lg font-semibold text-gray-700 mb-3">
          NEM market snapshot
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {(nemSnapshot ?? []).length === 0 ? (
            <p className="col-span-full text-gray-500 text-sm">
              No NEM data yet. Run the pipeline to populate nem_dispatch_prices
              and nem_market_snapshot.
            </p>
          ) : (
            (nemSnapshot ?? []).map((row) => (
              <div
                key={row.region_id}
                className="border border-gray-200 rounded-card bg-surface-card shadow-card p-4"
              >
                <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">
                  {row.region_id}
                </p>
                <p className={`text-2xl font-bold ${priceColor(row.rrp)}`}>
                  ${formatNumber(row.rrp, 2)}
                  <span className="text-xs font-normal text-gray-500 ml-1">
                    /MWh
                  </span>
                </p>
                <p className="text-sm text-gray-600 mt-1">
                  Demand: {formatNumber(row.total_demand_mw, 0)} MW
                </p>
                <p className="text-sm text-gray-600">
                  Generation: {formatNumber(row.available_generation_mw, 0)} MW
                </p>
              </div>
            ))
          )}
        </div>
      </section>

      {/* BOM Weather */}
      <section>
        <h3 className="font-heading text-lg font-semibold text-gray-700 mb-3">
          BOM current conditions
        </h3>
        <div className="overflow-x-auto border border-gray-200 rounded-card bg-surface-card shadow-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-gray-700 border-b-2 border-gray-200">
                <th className="px-4 py-3 font-semibold">Station</th>
                <th className="px-4 py-3 font-semibold">Temp</th>
                <th className="px-4 py-3 font-semibold">Feels like</th>
                <th className="px-4 py-3 font-semibold">Humidity</th>
                <th className="px-4 py-3 font-semibold">Wind</th>
                <th className="px-4 py-3 font-semibold">Rain since 9am</th>
                <th className="px-4 py-3 font-semibold">Observed</th>
              </tr>
            </thead>
            <tbody>
              {(bomCurrent ?? []).length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-6 text-center text-gray-500"
                  >
                    No BOM data yet. Run the pipeline to populate
                    bom_current_conditions.
                  </td>
                </tr>
              ) : (
                (bomCurrent ?? []).map((row) => (
                  <tr
                    key={row.station_name}
                    className="border-t border-gray-200 hover:bg-gray-100/50"
                  >
                    <td className="px-4 py-3 font-medium text-gray-700">
                      {row.station_name}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {row.air_temp_c != null
                        ? `${formatNumber(row.air_temp_c, 1)}\u00B0C`
                        : '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {row.apparent_temp_c != null
                        ? `${formatNumber(row.apparent_temp_c, 1)}\u00B0C`
                        : '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {row.relative_humidity_pct != null
                        ? `${formatNumber(row.relative_humidity_pct, 0)}%`
                        : '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {row.wind_speed_kmh != null
                        ? `${formatNumber(row.wind_speed_kmh, 0)} km/h ${row.wind_direction ?? ''}`
                        : '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {row.rainfall_mm != null
                        ? `${formatNumber(row.rainfall_mm, 1)} mm`
                        : '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {row.observation_timestamp ?? '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
