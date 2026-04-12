import { useState, useEffect } from "react";

const DATA_TYPES = ["DOUBLE", "STRING", "BOOLEAN", "INT", "TIMESTAMP"];

interface AttributeFormModalProps {
  open: boolean;
  mode: "create" | "edit";
  initial?: {
    attribute_id?: string;
    attribute_name?: string;
    data_type?: string;
    unit?: string | null;
    default_value?: string | null;
    is_required?: boolean;
    sort_order?: number;
    tag_pattern?: string | null;
  };
  onSubmit: (data: {
    attribute_id: string;
    attribute_name: string;
    data_type: string;
    unit: string | null;
    default_value: string | null;
    is_required: boolean;
    sort_order: number;
    tag_pattern: string | null;
  }) => void;
  onClose: () => void;
}

export default function AttributeFormModal({
  open,
  mode,
  initial,
  onSubmit,
  onClose,
}: AttributeFormModalProps) {
  const [attributeId, setAttributeId] = useState("");
  const [attributeName, setAttributeName] = useState("");
  const [dataType, setDataType] = useState("DOUBLE");
  const [unit, setUnit] = useState("");
  const [defaultValue, setDefaultValue] = useState("");
  const [isRequired, setIsRequired] = useState(false);
  const [sortOrder, setSortOrder] = useState(0);
  const [tagPattern, setTagPattern] = useState("");

  useEffect(() => {
    if (initial) {
      setAttributeId(initial.attribute_id ?? "");
      setAttributeName(initial.attribute_name ?? "");
      setDataType(initial.data_type ?? "DOUBLE");
      setUnit(initial.unit ?? "");
      setDefaultValue(initial.default_value ?? "");
      setIsRequired(initial.is_required ?? false);
      setSortOrder(initial.sort_order ?? 0);
      setTagPattern(initial.tag_pattern ?? "");
    } else {
      setAttributeId("");
      setAttributeName("");
      setDataType("DOUBLE");
      setUnit("");
      setDefaultValue("");
      setIsRequired(false);
      setSortOrder(0);
      setTagPattern("");
    }
  }, [initial, open]);

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      attribute_id: attributeId,
      attribute_name: attributeName,
      data_type: dataType,
      unit: unit || null,
      default_value: defaultValue || null,
      is_required: isRequired,
      sort_order: sortOrder,
      tag_pattern: tagPattern || null,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <form
        onSubmit={handleSubmit}
        className="bg-white border border-gray-200 rounded-lg p-6 w-full max-w-lg"
      >
        <h3 className="text-lg font-semibold mb-4">
          {mode === "create" ? "Add attribute" : "Edit attribute"}
        </h3>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">
              Attribute ID
            </label>
            <input
              type="text"
              value={attributeId}
              onChange={(e) =>
                setAttributeId(
                  e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""),
                )
              }
              disabled={mode === "edit"}
              required
              placeholder="e.g. attr_wind_speed"
              className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 disabled:opacity-50 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-600 mb-1">Name</label>
            <input
              type="text"
              value={attributeName}
              onChange={(e) => setAttributeName(e.target.value)}
              required
              className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">
                Data type
              </label>
              <select
                value={dataType}
                onChange={(e) => setDataType(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
              >
                {DATA_TYPES.map((dt) => (
                  <option key={dt} value={dt}>
                    {dt}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-600 mb-1">Unit</label>
              <input
                type="text"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="e.g. MW, %, C"
                className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">
                Default value
              </label>
              <input
                type="text"
                value={defaultValue}
                onChange={(e) => setDefaultValue(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs text-gray-600 mb-1">
                Sort order
              </label>
              <input
                type="number"
                value={sortOrder}
                onChange={(e) => setSortOrder(parseInt(e.target.value) || 0)}
                className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-600 mb-1">
              Tag binding (tag_name from parsed_tags)
            </label>
            <input
              type="text"
              placeholder="e.g. telemetry/soc_pct"
              value={tagPattern}
              onChange={(e) => setTagPattern(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 focus:outline-none focus:border-blue-500"
            />
          </div>

          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={isRequired}
              onChange={(e) => setIsRequired(e.target.checked)}
              className="rounded bg-gray-100 border-gray-200"
            />
            Required attribute
          </label>
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
            {mode === "create" ? "Add" : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}
