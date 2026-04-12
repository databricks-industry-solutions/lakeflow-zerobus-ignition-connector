import { useState, useEffect } from 'react';

const ASSET_TYPES = [
  'enterprise',
  'site',
  'wind_turbine',
  'battery_bess',
  'substation',
  'inverter',
];

interface TemplateFormModalProps {
  open: boolean;
  mode: 'create' | 'edit';
  initial?: { template_id?: string; template_name?: string; base_asset_type?: string; description?: string | null };
  onSubmit: (data: {
    template_id: string;
    template_name: string;
    base_asset_type: string;
    description: string | null;
  }) => void;
  onClose: () => void;
}

export default function TemplateFormModal({
  open,
  mode,
  initial,
  onSubmit,
  onClose,
}: TemplateFormModalProps) {
  const [templateId, setTemplateId] = useState('');
  const [templateName, setTemplateName] = useState('');
  const [baseAssetType, setBaseAssetType] = useState('site');
  const [description, setDescription] = useState('');

  useEffect(() => {
    if (initial) {
      setTemplateId(initial.template_id ?? '');
      setTemplateName(initial.template_name ?? '');
      setBaseAssetType(initial.base_asset_type ?? 'site');
      setDescription(initial.description ?? '');
    } else {
      setTemplateId('');
      setTemplateName('');
      setBaseAssetType('site');
      setDescription('');
    }
  }, [initial, open]);

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      template_id: templateId,
      template_name: templateName,
      base_asset_type: baseAssetType,
      description: description || null,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <form
        onSubmit={handleSubmit}
        className="bg-white border border-gray-200 rounded-lg p-6 w-full max-w-lg"
      >
        <h3 className="text-lg font-semibold mb-4">
          {mode === 'create' ? 'Create template' : 'Edit template'}
        </h3>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Template ID</label>
            <input
              type="text"
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
              disabled={mode === 'edit'}
              required
              placeholder="e.g. tpl_solar_panel"
              className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 disabled:opacity-50 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-600 mb-1">Name</label>
            <input
              type="text"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              required
              className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-600 mb-1">Base asset type</label>
            <select
              value={baseAssetType}
              onChange={(e) => setBaseAssetType(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
            >
              {ASSET_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-600 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm rounded bg-gray-100 text-gray-700 hover:bg-gray-700"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="px-4 py-2 text-sm rounded bg-blue-600 text-white hover:bg-blue-500"
          >
            {mode === 'create' ? 'Create' : 'Save'}
          </button>
        </div>
      </form>
    </div>
  );
}
