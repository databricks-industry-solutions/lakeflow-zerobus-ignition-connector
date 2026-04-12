import { useEffect, useMemo, useState } from "react";
import type { AssetTagCatalogRow } from "../services/api";

interface TagTreeNode {
  key: string;
  label: string;
  fullPath: string;
  children: TagTreeNode[];
  mappedCount: number;
  unmappedCount: number;
  leafTag?: AssetTagCatalogRow;
}

function buildTagTree(tags: AssetTagCatalogRow[]): TagTreeNode[] {
  const roots: TagTreeNode[] = [];

  const findOrCreate = (
    siblings: TagTreeNode[],
    label: string,
    fullPath: string,
  ): TagTreeNode => {
    const existing = siblings.find((n) => n.label === label);
    if (existing) return existing;
    const created: TagTreeNode = {
      key: fullPath,
      label,
      fullPath,
      children: [],
      mappedCount: 0,
      unmappedCount: 0,
    };
    siblings.push(created);
    return created;
  };

  const sorted = [...tags].sort((a, b) => a.tag_name.localeCompare(b.tag_name));
  for (const tag of sorted) {
    const parts = tag.tag_name.split("/").filter(Boolean);
    if (parts.length === 0) continue;

    let siblings = roots;
    let path = "";
    let current: TagTreeNode | undefined;
    for (const part of parts) {
      path = path ? `${path}/${part}` : part;
      current = findOrCreate(siblings, part, path);
      if (tag.is_mapped) current.mappedCount += 1;
      else current.unmappedCount += 1;
      siblings = current.children;
    }

    if (!current) continue;
    if (!current.leafTag || (!current.leafTag.is_mapped && tag.is_mapped)) {
      current.leafTag = tag;
    }
  }

  return roots;
}

function matchesSearch(node: TagTreeNode, lowerSearch: string): boolean {
  if (lowerSearch.length === 0) return true;
  if (node.fullPath.toLowerCase().includes(lowerSearch)) return true;
  return node.children.some((child) => matchesSearch(child, lowerSearch));
}

interface TagTreeNodeRowProps {
  node: TagTreeNode;
  depth: number;
  expandedIds: Set<string>;
  selectedTagName: string | null;
  search: string;
  onToggle: (id: string) => void;
  onSelectTagName: (tagName: string) => void;
}

function TagTreeNodeRow({
  node,
  depth,
  expandedIds,
  selectedTagName,
  search,
  onToggle,
  onSelectTagName,
}: TagTreeNodeRowProps) {
  if (!matchesSearch(node, search.trim().toLowerCase())) return null;

  const hasChildren = node.children.length > 0;
  const isExpanded = expandedIds.has(node.key);
  const isLeaf = !!node.leafTag && node.children.length === 0;
  const isSelected = isLeaf && node.leafTag?.tag_name === selectedTagName;

  const handleClick = () => {
    if (isLeaf && node.leafTag) {
      onSelectTagName(node.leafTag.tag_name);
      return;
    }
    if (hasChildren) {
      onToggle(node.key);
    }
  };

  return (
    <>
      <div
        className={`flex items-center gap-2 px-2 py-1.5 cursor-pointer text-sm rounded ${
          isSelected
            ? "bg-blue-100 border-l-2 border-blue-500 text-blue-900"
            : "text-gray-700 hover:bg-gray-100/70 border-l-2 border-transparent"
        }`}
        style={{ paddingLeft: `${depth * 14 + 8}px` }}
        onClick={handleClick}
      >
        <span className="w-4 text-center text-xs text-gray-500">
          {hasChildren ? (isExpanded ? "\u25BE" : "\u25B8") : ""}
        </span>
        <span className="truncate">{node.label}</span>
        <span className="ml-auto flex items-center gap-1">
          <span className="text-[10px] rounded bg-green-100 text-green-700 px-1.5 py-0.5">
            M:{node.mappedCount}
          </span>
          {node.unmappedCount > 0 && (
            <span className="text-[10px] rounded bg-amber-100 text-amber-700 px-1.5 py-0.5">
              U:{node.unmappedCount}
            </span>
          )}
        </span>
      </div>
      {hasChildren &&
        isExpanded &&
        node.children.map((child) => (
          <TagTreeNodeRow
            key={child.key}
            node={child}
            depth={depth + 1}
            expandedIds={expandedIds}
            selectedTagName={selectedTagName}
            search={search}
            onToggle={onToggle}
            onSelectTagName={onSelectTagName}
          />
        ))}
    </>
  );
}

interface TagTreeViewProps {
  tags: AssetTagCatalogRow[];
  selectedTagName: string | null;
  onSelectTagName: (tagName: string) => void;
}

export default function TagTreeView({
  tags,
  selectedTagName,
  onSelectTagName,
}: TagTreeViewProps) {
  const tree = useMemo(() => buildTagTree(tags), [tags]);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");

  useEffect(() => {
    setExpandedIds(new Set(tree.map((n) => n.key)));
  }, [tree]);

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
      <div className="p-2 border-b border-gray-200">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search tags..."
          className="w-full px-3 py-1.5 text-sm bg-gray-100 border border-gray-200 rounded text-gray-800 placeholder-gray-500 focus:outline-none focus:border-blue-500"
        />
      </div>
      <div className="flex-1 overflow-y-auto p-1">
        {tree.length === 0 ? (
          <div className="text-xs text-gray-500 p-2">
            No tags found for this asset.
          </div>
        ) : (
          tree.map((node) => (
            <TagTreeNodeRow
              key={node.key}
              node={node}
              depth={0}
              expandedIds={expandedIds}
              selectedTagName={selectedTagName}
              search={search}
              onToggle={onToggle}
              onSelectTagName={onSelectTagName}
            />
          ))
        )}
      </div>
    </div>
  );
}
