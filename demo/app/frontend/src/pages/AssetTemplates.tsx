import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import type { AssetTemplate, TemplateDetailRow } from "../services/api";
import TemplateCard from "../components/TemplateCard";
import TemplateFormModal from "../components/TemplateFormModal";
import AttributeFormModal from "../components/AttributeFormModal";
import ConfirmDialog from "../components/ConfirmDialog";

interface ParsedTemplate {
  template_id: string;
  template_name: string;
  description: string | null;
  base_asset_type: string;
  attributes: {
    attribute_id: string;
    attribute_name: string;
    data_type: string;
    unit: string | null;
    default_value: string | null;
    is_required: boolean;
    sort_order: number;
    tag_pattern: string | null;
  }[];
  assets: {
    asset_id: string;
    asset_name: string;
    asset_type: string;
    site_name: string;
  }[];
}

function parseTemplateDetail(
  rows: TemplateDetailRow[],
  assets: {
    asset_id: string;
    asset_name: string;
    asset_type: string;
    site_name: string;
  }[],
): ParsedTemplate | null {
  if (!rows.length) return null;
  const first = rows[0];
  return {
    template_id: first.template_id,
    template_name: first.template_name,
    description: first.description,
    base_asset_type: first.base_asset_type,
    attributes: rows
      .filter((r) => r.attribute_id)
      .map((r) => ({
        attribute_id: r.attribute_id!,
        attribute_name: r.attribute_name!,
        data_type: r.data_type!,
        unit: r.unit,
        default_value: r.default_value,
        is_required: r.is_required ?? false,
        sort_order: r.sort_order ?? 0,
        tag_pattern: r.tag_pattern ?? null,
      })),
    assets,
  };
}

export default function AssetTemplates() {
  const [templates, setTemplates] = useState<AssetTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Detail view
  const [detail, setDetail] = useState<ParsedTemplate | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Template form
  const [templateFormOpen, setTemplateFormOpen] = useState(false);
  const [templateFormMode, setTemplateFormMode] = useState<"create" | "edit">(
    "create",
  );

  // Attribute form
  const [attrFormOpen, setAttrFormOpen] = useState(false);
  const [attrFormMode, setAttrFormMode] = useState<"create" | "edit">("create");
  const [editingAttr, setEditingAttr] = useState<
    ParsedTemplate["attributes"][0] | undefined
  >();

  // Confirm dialogs
  const [deleteTemplateOpen, setDeleteTemplateOpen] = useState(false);
  const [deleteAttrId, setDeleteAttrId] = useState<string | null>(null);

  const loadTemplates = useCallback(async () => {
    try {
      const res = await api.assetFramework.getTemplates();
      setTemplates(res.data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load templates");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const loadDetail = async (templateId: string) => {
    setDetailLoading(true);
    try {
      const res = await api.assetFramework.getTemplate(templateId);
      const parsed = parseTemplateDetail(res.data.template, res.data.assets);
      setDetail(parsed);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCreateTemplate = () => {
    setTemplateFormMode("create");
    setTemplateFormOpen(true);
  };

  const handleEditTemplate = () => {
    setTemplateFormMode("edit");
    setTemplateFormOpen(true);
  };

  const handleTemplateSubmit = async (data: {
    template_id: string;
    template_name: string;
    base_asset_type: string;
    description: string | null;
  }) => {
    try {
      if (templateFormMode === "create") {
        await api.assetFramework.createTemplate(data);
      } else if (detail) {
        await api.assetFramework.updateTemplate(detail.template_id, {
          template_name: data.template_name,
          base_asset_type: data.base_asset_type,
          description: data.description ?? undefined,
        });
      }
      setTemplateFormOpen(false);
      await loadTemplates();
      if (templateFormMode === "create") {
        loadDetail(data.template_id);
      } else if (detail) {
        loadDetail(detail.template_id);
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Operation failed");
    }
  };

  const handleDeleteTemplate = async () => {
    if (!detail) return;
    try {
      await api.assetFramework.deleteTemplate(detail.template_id);
      setDeleteTemplateOpen(false);
      setDetail(null);
      await loadTemplates();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const handleAddAttribute = () => {
    setAttrFormMode("create");
    setEditingAttr(undefined);
    setAttrFormOpen(true);
  };

  const handleEditAttribute = (attr: ParsedTemplate["attributes"][0]) => {
    setAttrFormMode("edit");
    setEditingAttr(attr);
    setAttrFormOpen(true);
  };

  const handleAttrSubmit = async (data: {
    attribute_id: string;
    attribute_name: string;
    data_type: string;
    unit: string | null;
    default_value: string | null;
    is_required: boolean;
    sort_order: number;
    tag_pattern: string | null;
  }) => {
    if (!detail) return;
    try {
      if (attrFormMode === "create") {
        await api.assetFramework.createAttribute(detail.template_id, data);
      } else {
        await api.assetFramework.updateAttribute(
          detail.template_id,
          data.attribute_id,
          {
            attribute_name: data.attribute_name,
            data_type: data.data_type,
            unit: data.unit,
            default_value: data.default_value,
            is_required: data.is_required,
            sort_order: data.sort_order,
            tag_pattern: data.tag_pattern,
          },
        );
      }
      setAttrFormOpen(false);
      loadDetail(detail.template_id);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Operation failed");
    }
  };

  const handleDeleteAttribute = async () => {
    if (!detail || !deleteAttrId) return;
    try {
      await api.assetFramework.deleteAttribute(
        detail.template_id,
        deleteAttrId,
      );
      setDeleteAttrId(null);
      loadDetail(detail.template_id);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  };

  if (loading) {
    return <div className="text-gray-600 p-4">Loading templates...</div>;
  }

  if (error) {
    return <div className="text-red-400 p-4">Error: {error}</div>;
  }

  // Detail view
  if (detail) {
    return (
      <div>
        <button
          onClick={() => setDetail(null)}
          className="text-sm text-gray-600 hover:text-gray-800 mb-4"
        >
          &larr; Back to templates
        </button>

        {detailLoading ? (
          <div className="text-gray-600">Loading...</div>
        ) : (
          <div className="space-y-6">
            {/* Template header */}
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-xl font-semibold">
                  {detail.template_name}
                </h2>
                <p className="text-sm text-gray-600 mt-1">
                  <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">
                    {detail.template_id}
                  </span>
                  <span className="ml-3">
                    {detail.base_asset_type.replace(/_/g, " ")}
                  </span>
                </p>
                {detail.description && (
                  <p className="text-sm text-gray-600 mt-2">
                    {detail.description}
                  </p>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleEditTemplate}
                  className="px-3 py-1.5 text-sm rounded bg-gray-100 text-gray-700 hover:bg-gray-700"
                >
                  Edit
                </button>
                <button
                  onClick={() => setDeleteTemplateOpen(true)}
                  className="px-3 py-1.5 text-sm rounded bg-red-900/50 text-red-400 hover:bg-red-900/80"
                >
                  Delete
                </button>
              </div>
            </div>

            {/* Attributes table */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-700">
                  Attributes ({detail.attributes.length})
                </h3>
                <button
                  onClick={handleAddAttribute}
                  className="px-2 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-500"
                >
                  + Add attribute
                </button>
              </div>
              {detail.attributes.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-gray-500 border-b border-gray-200">
                      <th className="text-left py-1 font-normal w-8">#</th>
                      <th className="text-left py-1 font-normal">Name</th>
                      <th className="text-left py-1 font-normal">Type</th>
                      <th className="text-left py-1 font-normal">Unit</th>
                      <th className="text-left py-1 font-normal">Default</th>
                      <th className="text-left py-1 font-normal">Required</th>
                      <th className="text-left py-1 font-normal">
                        Tag binding
                      </th>
                      <th className="text-right py-1 font-normal">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.attributes.map((attr) => (
                      <tr
                        key={attr.attribute_id}
                        className="border-b border-gray-200/50"
                      >
                        <td className="py-1.5 text-gray-500 text-xs">
                          {attr.sort_order}
                        </td>
                        <td className="py-1.5 text-gray-700">
                          {attr.attribute_name}
                        </td>
                        <td className="py-1.5 text-gray-600 text-xs font-mono">
                          {attr.data_type}
                        </td>
                        <td className="py-1.5 text-gray-600 text-xs">
                          {attr.unit ?? "-"}
                        </td>
                        <td className="py-1.5 text-gray-600 text-xs font-mono">
                          {attr.default_value ?? "-"}
                        </td>
                        <td className="py-1.5 text-gray-600 text-xs">
                          {attr.is_required ? "Yes" : "No"}
                        </td>
                        <td className="py-1.5 text-xs font-mono text-gray-500">
                          {attr.tag_pattern ?? "-"}
                        </td>
                        <td className="py-1.5 text-right">
                          <button
                            onClick={() => handleEditAttribute(attr)}
                            className="text-xs text-blue-400 hover:text-blue-300 mr-2"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => setDeleteAttrId(attr.attribute_id)}
                            className="text-xs text-red-400 hover:text-red-300"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-gray-500">
                  No attributes defined yet.
                </p>
              )}
            </div>

            {/* Assets using template */}
            {detail.assets.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">
                  Assets using this template ({detail.assets.length})
                </h3>
                <div className="space-y-1">
                  {detail.assets.map((a) => (
                    <div
                      key={a.asset_id}
                      className="flex items-center gap-3 text-sm text-gray-600 py-1"
                    >
                      <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">
                        {a.asset_id}
                      </span>
                      <span>{a.asset_name}</span>
                      <span className="text-gray-500">{a.site_name}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Modals */}
        <TemplateFormModal
          open={templateFormOpen}
          mode={templateFormMode}
          initial={
            templateFormMode === "edit"
              ? {
                  template_id: detail.template_id,
                  template_name: detail.template_name,
                  base_asset_type: detail.base_asset_type,
                  description: detail.description,
                }
              : undefined
          }
          onSubmit={handleTemplateSubmit}
          onClose={() => setTemplateFormOpen(false)}
        />

        <AttributeFormModal
          open={attrFormOpen}
          mode={attrFormMode}
          initial={editingAttr}
          onSubmit={handleAttrSubmit}
          onClose={() => setAttrFormOpen(false)}
        />

        <ConfirmDialog
          open={deleteTemplateOpen}
          title="Delete template"
          message={`Delete "${detail.template_name}"? This cannot be undone. Templates with assets referencing them cannot be deleted.`}
          onConfirm={handleDeleteTemplate}
          onCancel={() => setDeleteTemplateOpen(false)}
        />

        <ConfirmDialog
          open={!!deleteAttrId}
          title="Delete attribute"
          message="Remove this attribute from the template? Existing asset attribute values will not be affected."
          onConfirm={handleDeleteAttribute}
          onCancel={() => setDeleteAttrId(null)}
        />
      </div>
    );
  }

  // List view
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-heading text-2xl font-semibold text-gray-900">
          Asset templates
        </h2>
        <button
          onClick={handleCreateTemplate}
          className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-500"
        >
          Create template
        </button>
      </div>

      {templates.length === 0 ? (
        <p className="text-gray-500">
          No templates found. Create one to get started.
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((t) => (
            <TemplateCard
              key={t.template_id}
              template={t}
              onClick={() => loadDetail(t.template_id)}
            />
          ))}
        </div>
      )}

      <TemplateFormModal
        open={templateFormOpen}
        mode="create"
        onSubmit={handleTemplateSubmit}
        onClose={() => setTemplateFormOpen(false)}
      />
    </div>
  );
}
