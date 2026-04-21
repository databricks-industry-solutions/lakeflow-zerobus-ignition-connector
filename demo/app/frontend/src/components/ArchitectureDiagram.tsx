const beforeComponents = [
  { label: 'SCADA', sub: 'Data source' },
  { label: 'Interface', sub: 'Exception reporting' },
  { label: 'Buffer', sub: 'Store & forward' },
  { label: 'Server', sub: 'SDT compression' },
  { label: 'Archive', sub: 'Proprietary storage' },
  { label: 'ETL', sub: 'Batch extract' },
  { label: 'Data Warehouse', sub: 'Analytics' },
  { label: 'BI', sub: 'Dashboards' },
];

const afterComponents = [
  { label: 'Ignition', sub: 'Exception reporting' },
  { label: 'Zerobus Connector', sub: 'SDT compression' },
  { label: 'Zerobus Ingest', sub: 'Serverless' },
  { label: 'Delta Lake', sub: 'Columnar compression' },
  { label: 'SQL / ML / BI', sub: 'Direct query' },
];

const highlights = ['No Kafka', 'No Buffer Nodes', 'No Archive Servers', 'Open Format'];

function Arrow() {
  return <span className="text-gray-500 mx-1">→</span>;
}

export default function ArchitectureDiagram() {
  return (
    <div className="space-y-6">
      {/* Before diagram */}
      <div className="bg-surface-card border border-gray-200 rounded-card p-4 shadow-card">
        <h3 className="font-heading text-sm font-semibold text-red-400 mb-3">
          Before (traditional stack)
        </h3>
        <div className="flex flex-wrap items-center gap-1">
          {beforeComponents.map((c, i) => (
            <span key={c.label} className="flex items-center">
              {i > 0 && <Arrow />}
              <span className="inline-flex flex-col items-center bg-gray-100 border border-gray-200 rounded px-3 py-2 text-center min-w-[90px]">
                <span className="text-sm font-medium text-gray-800">{c.label}</span>
                <span className="text-xs text-gray-500">{c.sub}</span>
              </span>
            </span>
          ))}
        </div>
        <p className="mt-2 text-xs text-gray-500">
          8 components - multiple failure points - proprietary format
        </p>
      </div>

      {/* After diagram */}
      <div className="bg-surface-card border border-gray-200 rounded-card p-4 shadow-card">
        <h3 className="font-heading text-sm font-semibold text-brand-green mb-3">
          After (Lakehouse)
        </h3>
        <div className="flex flex-wrap items-center gap-1">
          {afterComponents.map((c, i) => (
            <span key={c.label} className="flex items-center">
              {i > 0 && <Arrow />}
              <span className="inline-flex flex-col items-center bg-gray-100 border border-green-900 rounded px-3 py-2 text-center min-w-[90px]">
                <span className="text-sm font-medium text-gray-800">{c.label}</span>
                <span className="text-xs text-gray-500">{c.sub}</span>
              </span>
            </span>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {highlights.map((h) => (
            <span
              key={h}
              className="px-2 py-1 text-xs font-semibold bg-green-900/40 text-green-400 border border-green-800 rounded"
            >
              {h}
            </span>
          ))}
        </div>
        <p className="mt-2 text-xs text-gray-500">
          5 components - serverless ingest - open Delta format
        </p>
      </div>
    </div>
  );
}
