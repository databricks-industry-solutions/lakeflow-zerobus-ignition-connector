import type { TagEvent } from '../services/api';
import { qualityLabel, formatTimestamp, formatNumber } from '../utils/format';

interface EventStreamProps {
  events: TagEvent[];
}

export default function EventStream({ events }: EventStreamProps) {
  return (
    <div className="bg-surface-card border border-gray-200 rounded-card p-4 shadow-card">
      <h3 className="text-sm font-heading font-semibold text-gray-700 mb-3">
        Live event stream
      </h3>
      <div className="overflow-auto max-h-96">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b-2 border-gray-200">
              <th className="text-left py-2.5 px-2 font-semibold text-gray-700">Timestamp</th>
              <th className="text-left py-2.5 px-2 font-semibold text-gray-700">Asset</th>
              <th className="text-left py-2.5 px-2 font-semibold text-gray-700">Tag</th>
              <th className="text-right py-2.5 px-2 font-semibold text-gray-700">Value</th>
              <th className="text-left py-2.5 px-2 font-semibold text-gray-700">Quality</th>
              <th className="text-right py-2.5 px-2 font-semibold text-gray-700">Latency</th>
              <th className="text-center py-2.5 px-2 font-semibold text-gray-700">SDT</th>
            </tr>
          </thead>
          <tbody>
            {events.map((evt, i) => {
              const latencyMs =
                new Date(evt.ingest_timestamp).getTime() -
                new Date(evt.event_timestamp).getTime();
              return (
                <tr
                  key={`${evt.event_timestamp}-${evt.asset_id}-${evt.tag_name}-${i}`}
                  className={`border-b border-gray-100 hover:bg-gray-50/80 transition-colors duration-150 ${
                    i % 2 === 0 ? 'bg-surface-card' : 'bg-gray-50/50'
                  }`}
                >
                  <td className="py-1.5 px-2 text-gray-700 tabular-nums">
                    {formatTimestamp(evt.event_timestamp)}
                  </td>
                  <td className="py-1.5 px-2 text-gray-700">{evt.asset_id}</td>
                  <td className="py-1.5 px-2 text-gray-600">{evt.tag_name}</td>
                  <td className="py-1.5 px-2 text-right text-gray-900 tabular-nums">
                    {formatNumber(evt.tag_value)}
                  </td>
                  <td className="py-1.5 px-2 text-gray-600">
                    {qualityLabel(evt.quality)}
                  </td>
                  <td className="py-1.5 px-2 text-right text-gray-600 tabular-nums">
                    {formatNumber(latencyMs, 0)}ms
                  </td>
                  <td className="py-1.5 px-2 text-center">
                    {evt.sdt_compressed ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-brand-green/15 text-brand-green" title="Survived SDT">Post-SDT</span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-600" title="Pass-through (SDT off or non-numeric)">Raw</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
