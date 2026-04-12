import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import type {
  HierarchyAsset,
  AssetTemplate,
  AssetTagCatalogRow,
  AssetTagSummaryRow,
} from "../services/api";
import TreeView from "../components/TreeView";
import AssetDetailPanel from "../components/AssetDetailPanel";
import AssetFormModal from "../components/AssetFormModal";
import ConfirmDialog from "../components/ConfirmDialog";
import TagTreeView from "../components/TagTreeView";
import TagInspector from "../components/TagInspector";

export default function AssetHierarchy() {
  const [assets, setAssets] = useState<HierarchyAsset[]>([]);
  const [templates, setTemplates] = useState<AssetTemplate[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<HierarchyAsset | null>(
    null,
  );
  const [tagSummaryByAsset, setTagSummaryByAsset] = useState<
    Record<string, AssetTagSummaryRow>
  >({});
  const [assetTags, setAssetTags] = useState<AssetTagCatalogRow[]>([]);
  const [selectedTagName, setSelectedTagName] = useState<string | null>(null);
  const [tagsLoading, setTagsLoading] = useState(false);
  const [tagsError, setTagsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formParentId, setFormParentId] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [hierarchyRes, templatesRes] = await Promise.all([
        api.assetFramework.getHierarchy(),
        api.assetFramework.getTemplates(),
      ]);
      setAssets(hierarchyRes.data);
      setTemplates(templatesRes.data);
      try {
        const summaryRes = await api.assetFramework.getTagSummary();
        const next: Record<string, AssetTagSummaryRow> = {};
        for (const row of summaryRes.data) {
          next[row.asset_id] = row;
        }
        setTagSummaryByAsset(next);
      } catch {
        setTagSummaryByAsset({});
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAssetTags = useCallback(async (assetId: string) => {
    setTagsLoading(true);
    setTagsError(null);
    try {
      const res = await api.assetFramework.getAssetTags(assetId, 60, true);
      setAssetTags(res.data);
      setSelectedTagName((prev) => {
        if (prev && res.data.some((t) => t.tag_name === prev)) return prev;
        return res.data[0]?.tag_name ?? null;
      });
    } catch (err) {
      setAssetTags([]);
      setSelectedTagName(null);
      setTagsError(err instanceof Error ? err.message : "Failed to load tags");
    } finally {
      setTagsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Load detail when selection changes
  useEffect(() => {
    if (!selectedId) {
      setSelectedAsset(null);
      setAssetTags([]);
      setSelectedTagName(null);
      setTagsError(null);
      return;
    }
    api.assetFramework
      .getAsset(selectedId)
      .then((res) => setSelectedAsset(res.data))
      .catch(() => setSelectedAsset(null));
    loadAssetTags(selectedId);
  }, [selectedId, loadAssetTags]);

  const handleCreateRoot = () => {
    setFormMode("create");
    setFormParentId(null);
    setFormOpen(true);
  };

  const handleAddChild = () => {
    setFormMode("create");
    setFormParentId(selectedId);
    setFormOpen(true);
  };

  const handleEdit = () => {
    setFormMode("edit");
    setFormOpen(true);
  };

  const handleFormSubmit = async (data: {
    asset_id: string;
    asset_name: string;
    asset_type: string;
    parent_asset_id: string | null;
    template_id: string | null;
    site_name: string | null;
    description: string | null;
  }) => {
    try {
      if (formMode === "create") {
        await api.assetFramework.createAsset(data);
      } else {
        await api.assetFramework.updateAsset(data.asset_id, {
          asset_name: data.asset_name,
          asset_type: data.asset_type,
          template_id: data.template_id ?? undefined,
          site_name: data.site_name ?? undefined,
          description: data.description ?? undefined,
        });
      }
      setFormOpen(false);
      await loadData();
      if (formMode === "create") {
        setSelectedId(data.asset_id);
      } else if (selectedId) {
        // Reload detail
        const res = await api.assetFramework.getAsset(selectedId);
        setSelectedAsset(res.data);
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Operation failed");
    }
  };

  const handleDelete = async () => {
    if (!selectedId) return;
    try {
      await api.assetFramework.deleteAsset(selectedId);
      setConfirmOpen(false);
      setSelectedId(null);
      setSelectedAsset(null);
      await loadData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  };

  if (loading) {
    return <div className="text-gray-600 p-4">Loading hierarchy...</div>;
  }

  if (error) {
    return <div className="text-red-400 p-4">Error: {error}</div>;
  }

  const selectedTag = selectedTagName
    ? (assetTags.find((t) => t.tag_name === selectedTagName) ?? null)
    : null;

  return (
    <div className="flex h-[calc(100vh-3rem)] -m-6">
      {/* Left panel - tree */}
      <div className="w-80 flex-shrink-0 border-r border-gray-200 flex flex-col">
        <div className="flex items-center justify-between p-3 border-b border-gray-200">
          <h2 className="font-heading text-sm font-semibold text-gray-700">
            Asset hierarchy
          </h2>
          <button
            onClick={handleCreateRoot}
            className="px-2 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-500"
          >
            + New
          </button>
        </div>
        <TreeView
          assets={assets}
          selectedId={selectedId}
          tagSummaryByAsset={tagSummaryByAsset}
          onSelect={setSelectedId}
        />
      </div>

      {/* Right panel - detail */}
      <div className="flex-1 overflow-y-auto p-6">
        {selectedAsset ? (
          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,420px)] gap-6">
            <div className="min-w-0">
              <AssetDetailPanel
                asset={selectedAsset}
                templates={templates}
                onEdit={handleEdit}
                onAddChild={handleAddChild}
                onDelete={() => setConfirmOpen(true)}
                onRefresh={async () => {
                  await loadData();
                  if (selectedId) {
                    const res = await api.assetFramework.getAsset(selectedId);
                    setSelectedAsset(res.data);
                    await loadAssetTags(selectedId);
                  }
                }}
              />
            </div>
            <div className="min-w-0 flex flex-col gap-4">
              <div className="border border-gray-200 rounded-card bg-surface-card h-[460px] flex flex-col">
                <div className="px-4 py-3 border-b border-gray-200">
                  <h3 className="text-sm font-semibold text-gray-700">
                    Tag explorer
                  </h3>
                  <p className="text-xs text-gray-500 mt-1">
                    {tagsLoading
                      ? "Loading tags..."
                      : `${assetTags.length} tags in catalog`}
                  </p>
                </div>
                {tagsError && (
                  <div className="mx-3 mt-3 text-xs rounded border border-red-200 bg-red-50 text-red-700 px-2 py-1.5">
                    {tagsError}
                  </div>
                )}
                {tagsLoading ? (
                  <div className="flex-1 flex items-center justify-center text-sm text-gray-500">
                    Loading tag hierarchy...
                  </div>
                ) : (
                  <TagTreeView
                    tags={assetTags}
                    selectedTagName={selectedTagName}
                    onSelectTagName={setSelectedTagName}
                  />
                )}
              </div>
              <TagInspector selectedTag={selectedTag} />
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            Select an asset from the tree to view details
          </div>
        )}
      </div>

      {/* Modals */}
      <AssetFormModal
        open={formOpen}
        mode={formMode}
        asset={formMode === "edit" ? selectedAsset : null}
        assets={assets}
        templates={templates}
        parentId={formParentId}
        onSubmit={handleFormSubmit}
        onClose={() => setFormOpen(false)}
      />

      <ConfirmDialog
        open={confirmOpen}
        title="Delete asset"
        message={`This will deactivate "${selectedAsset?.asset_name}" and all its children. This can be undone by reactivating in the database.`}
        onConfirm={handleDelete}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
