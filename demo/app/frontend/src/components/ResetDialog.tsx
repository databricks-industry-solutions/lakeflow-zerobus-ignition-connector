import { useState } from "react";
import { api } from "../services/api";

export default function ResetDialog() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleReset = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.resetDemo();
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        onClick={() => {
          setError(null);
          setOpen(true);
        }}
        className="px-3 py-1.5 rounded-card text-sm font-medium bg-brand-red/20 text-brand-red hover:bg-brand-red/30 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-red focus-visible:ring-offset-2"
      >
        Reset Demo
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-surface-card border border-gray-200 rounded-card p-6 max-w-md w-full mx-4 shadow-card">
            <h3 className="font-heading text-lg font-semibold text-gray-900 mb-2">
              Reset demo?
            </h3>
            <p className="text-gray-600 text-sm mb-6">
              Are you sure? This will truncate all demo tables and restart the
              simulator.
            </p>
            {error && <p className="text-sm text-red-700 mb-4">{error}</p>}
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setOpen(false)}
                className="px-4 py-2 rounded-card text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-databricks-primary focus-visible:ring-offset-2"
              >
                Cancel
              </button>
              <button
                onClick={handleReset}
                disabled={loading}
                className="px-4 py-2 rounded-card text-sm font-medium bg-brand-red text-white hover:bg-brand-red/80 disabled:opacity-50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-red focus-visible:ring-offset-2"
              >
                {loading ? "Resetting..." : "Confirm Reset"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
