import type { AssetTagCatalogRow } from "../services/api";
import { formatNumber, formatTimestamp, qualityLabel } from "../utils/format";

interface TagInspectorProps {
  selectedTag: AssetTagCatalogRow | null;
}

function formatLiveValue(tag: AssetTagCatalogRow): string {
  if (tag.live_value != null) return formatNumber(tag.live_value);
  if (tag.live_value_str) return tag.live_value_str;
  return "-";
}

export default function TagInspector({ selectedTag }: TagInspectorProps) {
  if (!selectedTag) {
    return (
      <div className="border border-gray-200 rounded-card bg-surface-card p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">
          Tag inspector
        </h3>
        <p className="text-sm text-gray-500">
          Select a tag from the tree to inspect its latest value and mapping.
        </p>
      </div>
    );
  }

  return (
    <div className="border border-gray-200 rounded-card bg-surface-card p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Tag inspector</h3>
          <p className="text-xs font-mono text-gray-700 mt-1">
            {selectedTag.tag_name}
          </p>
        </div>
        <span
          className={`text-xs px-2 py-1 rounded ${
            selectedTag.is_mapped
              ? "bg-green-100 text-green-700"
              : "bg-amber-100 text-amber-700"
          }`}
        >
          {selectedTag.is_mapped ? "Mapped" : "Unmapped"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <span className="text-xs text-gray-500">Live value</span>
          <p className="text-gray-900">{formatLiveValue(selectedTag)}</p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Quality</span>
          <p className="text-gray-900">{qualityLabel(selectedTag.quality)}</p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Last update</span>
          <p className="text-gray-900">
            {selectedTag.live_at ? formatTimestamp(selectedTag.live_at) : "-"}
          </p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Source domain</span>
          <p className="text-gray-900">{selectedTag.source_domain ?? "-"}</p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Unit</span>
          <p className="text-gray-900">{selectedTag.unit ?? "-"}</p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Compression ratio</span>
          <p className="text-gray-900">
            {formatNumber(selectedTag.compression_ratio)}
          </p>
        </div>
      </div>

      {selectedTag.tag_path && (
        <div>
          <span className="text-xs text-gray-500">Mapped path</span>
          <p className="text-xs font-mono text-gray-700 mt-1 break-all">
            {selectedTag.tag_path}
          </p>
        </div>
      )}
    </div>
  );
}
