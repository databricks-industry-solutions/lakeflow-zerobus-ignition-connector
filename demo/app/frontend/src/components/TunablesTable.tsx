const rows = [
  {
    parameter: 'Batch size',
    defaultVal: '500',
    range: '1 - 10,000',
    purpose: 'Events per publish batch',
  },
  {
    parameter: 'Flush interval',
    defaultVal: '2s',
    range: '100ms - 60s',
    purpose: 'Max buffer time before publish',
  },
  {
    parameter: 'Queue size',
    defaultVal: '10,000',
    range: 'Configurable',
    purpose: 'In-memory event buffer',
  },
  {
    parameter: 'Disk spool',
    defaultVal: '1 GiB',
    range: 'Configurable',
    purpose: 'Store-and-forward overflow',
  },
  {
    parameter: 'Rate limit',
    defaultVal: '1,000 eps',
    range: 'Configurable',
    purpose: 'Max events per second',
  },
];

export default function TunablesTable() {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Connector tunables
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 px-3 text-gray-600 font-medium">Parameter</th>
              <th className="text-left py-2 px-3 text-gray-600 font-medium">Default</th>
              <th className="text-left py-2 px-3 text-gray-600 font-medium">Range</th>
              <th className="text-left py-2 px-3 text-gray-600 font-medium">Purpose</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.parameter} className="border-b border-gray-200">
                <td className="py-2 px-3 text-gray-700 font-medium">{r.parameter}</td>
                <td className="py-2 px-3 text-databricks-primary font-mono">{r.defaultVal}</td>
                <td className="py-2 px-3 text-gray-600">{r.range}</td>
                <td className="py-2 px-3 text-gray-600">{r.purpose}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
