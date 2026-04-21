import { useMemo, useState } from "react";
import type { HierarchyAsset } from "../services/api";

const TYPE_ICONS: Record<string, string> = {
  enterprise: "\u{1F3E2}", // office building
  site: "\u{1F4CD}", // map pin
  battery_bess: "\u{1F50B}", // battery
  wind_turbine: "\u{1F32C}", // wind
  substation: "\u{26A1}", // zap
  inverter: "\u{1F9AE}", // circuit
};

function getIcon(type: string) {
  return TYPE_ICONS[type] ?? "\u{1F4E6}"; // package fallback
}

interface TreeNode {
  asset: HierarchyAsset;
  children: TreeNode[];
}

function buildTree(assets: HierarchyAsset[]): TreeNode[] {
  const map = new Map<string, TreeNode>();
  const roots: TreeNode[] = [];

  for (const asset of assets) {
    map.set(asset.asset_id, { asset, children: [] });
  }

  for (const asset of assets) {
    const node = map.get(asset.asset_id)!;
    if (asset.parent_asset_id && map.has(asset.parent_asset_id)) {
      map.get(asset.parent_asset_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}

function matchesSearch(node: TreeNode, term: string): boolean {
  const lower = term.toLowerCase();
  if (
    node.asset.asset_name.toLowerCase().includes(lower) ||
    node.asset.asset_id.toLowerCase().includes(lower) ||
    node.asset.asset_type.toLowerCase().includes(lower)
  ) {
    return true;
  }
  return node.children.some((child) => matchesSearch(child, term));
}

interface TreeNodeRowProps {
  node: TreeNode;
  depth: number;
  expandedIds: Set<string>;
  selectedId: string | null;
  searchTerm: string;
  showOnlyWithData: boolean;
  tagSummaryByAsset?: Record<
    string,
    { mapped_tag_count: number; unmapped_tag_count: number }
  >;
  onToggle: (id: string) => void;
  onSelect: (id: string) => void;
}

function TreeNodeRow({
  node,
  depth,
  expandedIds,
  selectedId,
  searchTerm,
  showOnlyWithData,
  tagSummaryByAsset,
  onToggle,
  onSelect,
}: TreeNodeRowProps) {
  const visibleChildren = showOnlyWithData && tagSummaryByAsset
    ? node.children.filter((child) => hasTagData(child, tagSummaryByAsset))
    : node.children;
  const hasChildren = visibleChildren.length > 0;
  const isExpanded = expandedIds.has(node.asset.asset_id);
  const isSelected = selectedId === node.asset.asset_id;
  const tagSummary = tagSummaryByAsset?.[node.asset.asset_id];

  if (searchTerm && !matchesSearch(node, searchTerm)) {
    return null;
  }

  return (
    <>
      <div
        className={`flex items-center gap-2 px-2 py-1.5 cursor-pointer text-sm rounded ${
          isSelected
            ? "bg-blue-50 border-l-2 border-blue-500 text-gray-900 font-medium"
            : "text-gray-800 hover:bg-gray-50 border-l-2 border-transparent"
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => onSelect(node.asset.asset_id)}
      >
        <span
          className={`w-4 text-center text-xs text-gray-500 ${hasChildren ? "cursor-pointer" : ""}`}
          onClick={(e) => {
            if (hasChildren) {
              e.stopPropagation();
              onToggle(node.asset.asset_id);
            }
          }}
        >
          {hasChildren ? (isExpanded ? "\u25BE" : "\u25B8") : ""}
        </span>
        <span className="text-base leading-none">
          {getIcon(node.asset.asset_type)}
        </span>
        <span className="truncate">{node.asset.asset_name}</span>
        {tagSummary && (
          <span className="ml-auto flex items-center gap-1">
            <span className="text-[10px] rounded bg-green-100 text-green-700 px-1.5 py-0.5">
              M:{tagSummary.mapped_tag_count}
            </span>
            {tagSummary.unmapped_tag_count > 0 && (
              <span className="text-[10px] rounded bg-amber-100 text-amber-700 px-1.5 py-0.5">
                U:{tagSummary.unmapped_tag_count}
              </span>
            )}
          </span>
        )}
        {node.asset.child_count > 0 && (
          <span className="text-xs text-gray-500 ml-auto">
            {node.asset.child_count}
          </span>
        )}
      </div>
      {isExpanded &&
        visibleChildren.map((child) => (
          <TreeNodeRow
            key={child.asset.asset_id}
            node={child}
            depth={depth + 1}
            expandedIds={expandedIds}
            selectedId={selectedId}
            searchTerm={searchTerm}
            showOnlyWithData={showOnlyWithData}
            tagSummaryByAsset={tagSummaryByAsset}
            onToggle={onToggle}
            onSelect={onSelect}
          />
        ))}
    </>
  );
}

/** Check if a node or any descendant has tag data. */
function hasTagData(
  node: TreeNode,
  summary: Record<string, { mapped_tag_count: number; unmapped_tag_count: number }> | undefined,
): boolean {
  if (!summary) return true;
  const s = summary[node.asset.asset_id];
  if (s && (s.mapped_tag_count > 0 || s.unmapped_tag_count > 0)) return true;
  return node.children.some((child) => hasTagData(child, summary));
}

interface TreeViewProps {
  assets: HierarchyAsset[];
  selectedId: string | null;
  tagSummaryByAsset?: Record<
    string,
    { mapped_tag_count: number; unmapped_tag_count: number }
  >;
  onSelect: (id: string) => void;
}

export default function TreeView({
  assets,
  selectedId,
  tagSummaryByAsset,
  onSelect,
}: TreeViewProps) {
  const tree = useMemo(() => buildTree(assets), [assets]);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => {
    // Start with root nodes expanded
    const roots = new Set<string>();
    for (const a of assets) {
      if (!a.parent_asset_id) roots.add(a.asset_id);
    }
    return roots;
  });
  const [search, setSearch] = useState("");
  const [showOnlyWithData, setShowOnlyWithData] = useState(true);

  // Filter tree to only nodes with tag data (if toggle is on)
  const filteredTree = useMemo(() => {
    if (!showOnlyWithData || !tagSummaryByAsset) return tree;
    return tree.filter((node) => hasTagData(node, tagSummaryByAsset));
  }, [tree, showOnlyWithData, tagSummaryByAsset]);

  const onToggle = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 space-y-2">
        <input
          type="text"
          placeholder="Search assets..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full px-3 py-1.5 text-sm bg-gray-50 border border-gray-200 rounded text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500"
        />
        {tagSummaryByAsset && Object.keys(tagSummaryByAsset).length > 0 && (
          <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showOnlyWithData}
              onChange={(e) => setShowOnlyWithData(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Only show assets with tag data
          </label>
        )}
      </div>
      <div className="flex-1 overflow-y-auto px-1">
        {filteredTree.map((node) => (
          <TreeNodeRow
            key={node.asset.asset_id}
            node={node}
            depth={0}
            expandedIds={expandedIds}
            selectedId={selectedId}
            searchTerm={search}
            showOnlyWithData={showOnlyWithData}
            tagSummaryByAsset={tagSummaryByAsset}
            onToggle={onToggle}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  );
}
