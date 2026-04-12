import { useState, useEffect } from 'react';
import type { HierarchyAsset, AssetTemplate } from '../services/api';

const ASSET_TYPES = [
  'enterprise',
  'site',
  'wind_turbine',
  'battery_bess',
  'substation',
  'inverter',
];

interface AssetFormModalProps {
  open: boolean;
  mode: 'create' | 'edit';
  asset?: HierarchyAsset | null;
  assets: HierarchyAsset[];
  templates: AssetTemplate[];
  parentId?: string | null;
  onSubmit: (data: {
    asset_id: string;
    asset_name: string;
    asset_type: string;
    parent_asset_id: string | null;
    template_id: string | null;
    site_name: string | null;
    description: string | null;
  }) => void;
  onClose: () => void;
}

export default function AssetFormModal({
  open,
  mode,
  asset,
  assets,
  templates,
  parentId,
  onSubmit,
  onClose,
}: AssetFormModalProps) {
  const [assetId, setAssetId] = useState('');
  const [assetName, setAssetName] = useState('');
  const [assetType, setAssetType] = useState('site');
  const [parentAssetId, setParentAssetId] = useState<string>('');
  const [templateId, setTemplateId] = useState<string>('');
  const [siteName, setSiteName] = useState('');
  const [description, setDescription] = useState('');

  useEffect(() => {
    if (mode === 'edit' && asset) {
      setAssetId(asset.asset_id);
      setAssetName(asset.asset_name);
      setAssetType(asset.asset_type);
      setParentAssetId(asset.parent_asset_id ?? '');
      setTemplateId(asset.template_id ?? '');
      setSiteName(asset.site_name ?? '');
      setDescription(asset.description ?? '');
    } else {
      setAssetId('');
      setAssetName('');
      setAssetType('site');
      setParentAssetId(parentId ?? '');
      setTemplateId('');
      setSiteName('');
      setDescription('');
    }
  }, [mode, asset, parentId, open]);

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      asset_id: assetId,
      asset_name: assetName,
      asset_type: assetType,
      parent_asset_id: parentAssetId || null,
      template_id: templateId || null,
      site_name: siteName || null,
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
          {mode === 'create' ? 'Create asset' : 'Edit asset'}
        </h3>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Asset ID</label>
            <input
              type="text"
              value={assetId}
              onChange={(e) => setAssetId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
              disabled={mode === 'edit'}
              required
              placeholder="e.g. hexham_t04"
              className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 disabled:opacity-50 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-600 mb-1">Name</label>
            <input
              type="text"
              value={assetName}
              onChange={(e) => setAssetName(e.target.value)}
              required
              className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Type</label>
              <select
                value={assetType}
                onChange={(e) => setAssetType(e.target.value)}
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
              <label className="block text-xs text-gray-600 mb-1">Parent</label>
              <select
                value={parentAssetId}
                onChange={(e) => setParentAssetId(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
              >
                <option value="">None (root)</option>
                {assets
                  .filter((a) => a.asset_id !== assetId)
                  .map((a) => (
                    <option key={a.asset_id} value={a.asset_id}>
                      {'  '.repeat(a.depth)}{a.asset_name}
                    </option>
                  ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Template</label>
              <select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
              >
                <option value="">None</option>
                {templates.map((t) => (
                  <option key={t.template_id} value={t.template_id}>
                    {t.template_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-600 mb-1">Site</label>
              <input
                type="text"
                value={siteName}
                onChange={(e) => setSiteName(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
              />
            </div>
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
