import ArchitectureDiagram from '../components/ArchitectureDiagram';
import ComparisonTable from '../components/ComparisonTable';

export default function Architecture() {
  return (
    <div>
      <h2 className="font-heading text-2xl font-semibold text-gray-900 mb-4">Architecture</h2>
      <p className="text-gray-600 mb-6 max-w-2xl">
        What we offer: <strong className="text-gray-800">higher granularity</strong> (sub-second to 1s without per-tag cost explosion), OT and market data in one place, your models in Python/MLflow on the same Delta tables, and one pipeline from ingest to revenue-at-risk — no separate ETL project.
      </p>

      {/* Before/After diagrams */}
      <div className="mb-6">
        <ArchitectureDiagram />
      </div>

      {/* Operational overhead comparison table */}
      <ComparisonTable />
    </div>
  );
}
