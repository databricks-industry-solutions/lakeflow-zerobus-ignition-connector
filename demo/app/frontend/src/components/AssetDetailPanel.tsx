import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import type {
  HierarchyAsset,
  AssetTemplate,
  AssetAttributeValue,
  LiveAttributeValue,
  ChildAggregationRow,
} from "../services/api";
import { usePolling } from "../hooks/usePolling";

interface AssetDetailPanelProps {
  asset: HierarchyAsset;
  templates: AssetTemplate[];
  onEdit: () => void;
  onAddChild: () => void;
  onDelete: () => void;
  onRefresh: () => void;
}

export default function AssetDetailPanel({
  asset,
  templates,
  onEdit,
  onAddChild,
  onDelete,
  onRefresh,
}: AssetDetailPanelProps) {
  const [attributes, setAttributes] = useState<AssetAttributeValue[]>([]);
  const [editingAttrs, setEditingAttrs] = useState(false);
  const [attrValues, setAttrValues] = useState<Record<string, string>>({});
  const [applyingTemplate, setApplyingTemplate] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");

  const hasBoundAttrs = attributes.some((a) => a.tag_pattern);
  const { data: liveValues } = usePolling<LiveAttributeValue[]>({
    fetcher: () =>
      api.assetFramework.getLiveAttributes(asset.asset_id).then((r) => r.data),
    intervalMs: 5000,
    enabled: hasBoundAttrs,
  });
  const liveMap = new Map(liveValues?.map((v) => [v.attribute_id, v]) ?? []);

  // Aggregation across child assets (only when asset has children)
  const hasChildren = (asset.child_count ?? 0) > 0;
  const { data: aggregation } = usePolling<ChildAggregationRow[]>({
    fetcher: () =>
      api.assetFramework.getChildAggregation(asset.asset_id, 10).then((r) => r.data),
    intervalMs: 10000,
    enabled: hasChildren,
  });

  const loadAttributes = useCallback(async () => {
    try {
      const res = await api.assetFramework.getAssetAttributes(asset.asset_id);
      setAttributes(res.data);
      const vals: Record<string, string> = {};
      for (const a of res.data) {
        vals[a.attribute_id] = a.value ?? "";
      }
      setAttrValues(vals);
    } catch {
      setAttributes([]);
    }
  }, [asset.asset_id]);

  useEffect(() => {
    loadAttributes();
  }, [loadAttributes]);

  async function handleSaveAttributes() {
    const values = Object.entries(attrValues).map(([attribute_id, value]) => ({
      attribute_id,
      value: value || null,
    }));
    await api.assetFramework.updateAssetAttributes(asset.asset_id, values);
    setEditingAttrs(false);
    loadAttributes();
  }

  async function handleApplyTemplate() {
    if (!selectedTemplateId) return;
    await api.assetFramework.applyTemplate(asset.asset_id, selectedTemplateId);
    setApplyingTemplate(false);
    setSelectedTemplateId("");
    onRefresh();
    loadAttributes();
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold">{asset.asset_name}</h2>
          <p className="text-sm text-gray-600 mt-1">
            <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">
              {asset.asset_id}
            </span>
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onEdit}
            className="px-3 py-1.5 text-sm rounded bg-gray-100 text-gray-700 hover:bg-gray-700"
          >
            Edit
          </button>
          <button
            onClick={onAddChild}
            className="px-3 py-1.5 text-sm rounded bg-gray-100 text-gray-700 hover:bg-gray-700"
          >
            Add child
          </button>
          <button
            onClick={onDelete}
            className="px-3 py-1.5 text-sm rounded bg-red-900/50 text-red-400 hover:bg-red-900/80"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <span className="text-xs text-gray-500">Type</span>
          <p className="text-sm">{asset.asset_type.replace(/_/g, " ")}</p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Site</span>
          <p className="text-sm">{asset.site_name ?? "-"}</p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Template</span>
          <p className="text-sm">{asset.template_name ?? "None"}</p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Parent</span>
          <p className="text-sm font-mono text-xs">
            {asset.parent_asset_id ?? "Root"}
          </p>
        </div>
        {asset.capacity_mw != null && (
          <div>
            <span className="text-xs text-gray-500">Capacity</span>
            <p className="text-sm">{asset.capacity_mw} MW</p>
          </div>
        )}
        {asset.tag_count != null && (
          <div>
            <span className="text-xs text-gray-500">Tags</span>
            <p className="text-sm">{asset.tag_count}</p>
          </div>
        )}
      </div>

      {asset.description && (
        <div>
          <span className="text-xs text-gray-500">Description</span>
          <p className="text-sm text-gray-700">{asset.description}</p>
        </div>
      )}

      {/* Apply template */}
      {!applyingTemplate ? (
        <button
          onClick={() => setApplyingTemplate(true)}
          className="text-sm text-blue-400 hover:text-blue-300"
        >
          Apply template...
        </button>
      ) : (
        <div className="flex gap-2 items-center">
          <select
            value={selectedTemplateId}
            onChange={(e) => setSelectedTemplateId(e.target.value)}
            className="flex-1 px-3 py-1.5 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800"
          >
            <option value="">Select template</option>
            {templates.map((t) => (
              <option key={t.template_id} value={t.template_id}>
                {t.template_name}
              </option>
            ))}
          </select>
          <button
            onClick={handleApplyTemplate}
            disabled={!selectedTemplateId}
            className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50"
          >
            Apply
          </button>
          <button
            onClick={() => {
              setApplyingTemplate(false);
              setSelectedTemplateId("");
            }}
            className="px-3 py-1.5 text-sm rounded bg-gray-100 text-gray-700 hover:bg-gray-700"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Child aggregation */}
      {hasChildren && aggregation && aggregation.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">
            Roll-up across children
          </h3>
          <p className="text-xs text-gray-500 mb-3">
            Latest value per child asset, aggregated. Only signals appearing on 2+ children are shown.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 border-b border-gray-200">
                  <th className="text-left py-1.5 font-normal">Signal</th>
                  <th className="text-right py-1.5 font-normal">Avg</th>
                  <th className="text-right py-1.5 font-normal">Min</th>
                  <th className="text-right py-1.5 font-normal">Max</th>
                  <th className="text-right py-1.5 font-normal">Assets</th>
                </tr>
              </thead>
              <tbody>
                {aggregation.map((row) => (
                  <tr
                    key={row.tag_name}
                    className="border-b border-gray-100 hover:bg-gray-50"
                  >
                    <td className="py-1.5 font-mono text-xs text-gray-800">
                      {row.tag_name}
                    </td>
                    <td className="py-1.5 text-right font-mono text-xs text-brand-green font-medium">
                      {row.avg_value}
                    </td>
                    <td className="py-1.5 text-right font-mono text-xs text-gray-600">
                      {row.min_value}
                    </td>
                    <td className="py-1.5 text-right font-mono text-xs text-gray-600">
                      {row.max_value}
                    </td>
                    <td className="py-1.5 text-right text-xs text-gray-500">
                      {row.asset_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Attribute values */}
      {attributes.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-700">Attributes</h3>
            {!editingAttrs ? (
              <button
                onClick={() => setEditingAttrs(true)}
                className="text-xs text-blue-400 hover:text-blue-300"
              >
                Edit values
              </button>
            ) : (
              <div className="flex gap-2">
                <button
                  onClick={handleSaveAttributes}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  Save
                </button>
                <button
                  onClick={() => {
                    setEditingAttrs(false);
                    loadAttributes();
                  }}
                  className="text-xs text-gray-600 hover:text-gray-700"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-200">
                <th className="text-left py-1 font-normal">Attribute</th>
                <th className="text-left py-1 font-normal">Value</th>
                <th className="text-left py-1 font-normal">Unit</th>
                <th className="text-left py-1 font-normal">Type</th>
                <th className="text-left py-1 font-normal">Live value</th>
              </tr>
            </thead>
            <tbody>
              {attributes.map((attr) => (
                <tr
                  key={attr.attribute_id}
                  className="border-b border-gray-200/50"
                >
                  <td className="py-1.5 text-gray-700">
                    {attr.attribute_name}
                    {attr.is_required && (
                      <span className="text-red-400 ml-1">*</span>
                    )}
                  </td>
                  <td className="py-1.5">
                    {editingAttrs ? (
                      <input
                        type="text"
                        value={attrValues[attr.attribute_id] ?? ""}
                        onChange={(e) =>
                          setAttrValues((prev) => ({
                            ...prev,
                            [attr.attribute_id]: e.target.value,
                          }))
                        }
                        className="w-full px-2 py-0.5 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800"
                      />
                    ) : (
                      <span className="font-mono text-xs">
                        {attr.value ?? "-"}
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 text-gray-500 text-xs">
                    {attr.unit ?? ""}
                  </td>
                  <td className="py-1.5 text-gray-500 text-xs">
                    {attr.data_type}
                  </td>
                  <td className="py-1.5">
                    {attr.tag_pattern ? (
                      liveMap.get(attr.attribute_id)?.live_value != null ? (
                        <span className="font-mono text-xs text-green-600">
                          {liveMap
                            .get(attr.attribute_id)!
                            .live_value!.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">-</span>
                      )
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
