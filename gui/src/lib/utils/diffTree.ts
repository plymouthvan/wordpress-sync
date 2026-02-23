import type { DiffEntry } from '$lib/types';

export interface TreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  change?: 'added' | 'modified' | 'deleted';
  size?: number;
  children: TreeNode[];
  selected: boolean;
  expanded: boolean;
}

/**
 * Build a tree structure from a flat list of DiffEntry paths.
 * Optionally accepts a previous tree to preserve expanded states.
 */
export function buildTree(entries: DiffEntry[], previousTree?: TreeNode): TreeNode {
  // Collect expanded paths from previous tree to preserve state
  const expandedPaths = new Set<string>();
  if (previousTree) {
    collectExpandedPaths(previousTree, expandedPaths);
  }

  const root: TreeNode = {
    name: '/',
    path: '',
    type: 'directory',
    children: [],
    selected: true,
    expanded: true,
  };

  for (const entry of entries) {
    const parts = entry.path.split('/').filter((p) => p);
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const isLast = i === parts.length - 1;
      const name = parts[i];
      const partPath = parts.slice(0, i + 1).join('/');

      let child = current.children.find((c) => c.name === name);
      if (!child) {
        child = {
          name,
          path: partPath,
          type: isLast ? entry.type : 'directory',
          change: isLast ? entry.change : undefined,
          size: isLast ? entry.size : undefined,
          children: [],
          selected: entry.selected,
          expanded: expandedPaths.has(partPath),
        };
        current.children.push(child);
      } else if (isLast) {
        // Update existing intermediate node with leaf data
        child.change = entry.change;
        child.size = entry.size;
        child.type = entry.type;
        child.selected = entry.selected;
      }
      current = child;
    }
  }

  // Sort: directories first, then alphabetically
  sortTree(root);
  return root;
}

function collectExpandedPaths(node: TreeNode, paths: Set<string>): void {
  if (node.expanded && node.children.length > 0) {
    paths.add(node.path);
  }
  for (const child of node.children) {
    collectExpandedPaths(child, paths);
  }
}

function sortTree(node: TreeNode): void {
  node.children.sort((a, b) => {
    if (a.children.length > 0 && b.children.length === 0) return -1;
    if (a.children.length === 0 && b.children.length > 0) return 1;
    return a.name.localeCompare(b.name);
  });
  for (const child of node.children) {
    sortTree(child);
  }
}

/**
 * Count added, modified, deleted entries in a subtree.
 */
export function getAggregatedCounts(node: TreeNode): {
  added: number;
  modified: number;
  deleted: number;
} {
  const counts = { added: 0, modified: 0, deleted: 0 };

  if (node.children.length === 0) {
    // Leaf node
    if (node.change === 'added') counts.added = 1;
    else if (node.change === 'modified') counts.modified = 1;
    else if (node.change === 'deleted') counts.deleted = 1;
    return counts;
  }

  for (const child of node.children) {
    const childCounts = getAggregatedCounts(child);
    counts.added += childCounts.added;
    counts.modified += childCounts.modified;
    counts.deleted += childCounts.deleted;
  }

  return counts;
}

/**
 * Determine the tri-state checkbox state from a node's children.
 */
export function getCheckboxState(
  node: TreeNode,
): 'checked' | 'unchecked' | 'indeterminate' {
  if (node.children.length === 0) {
    return node.selected ? 'checked' : 'unchecked';
  }

  const leaves = getAllLeaves(node);
  const selectedCount = leaves.filter((l) => l.selected).length;

  if (selectedCount === 0) return 'unchecked';
  if (selectedCount === leaves.length) return 'checked';
  return 'indeterminate';
}

/**
 * Get all leaf nodes in a subtree.
 */
export function getAllLeaves(node: TreeNode): TreeNode[] {
  if (node.children.length === 0) return [node];
  const leaves: TreeNode[] = [];
  for (const child of node.children) {
    leaves.push(...getAllLeaves(child));
  }
  return leaves;
}

/**
 * Set the selected state of a node and all its descendants.
 */
export function setNodeSelected(node: TreeNode, selected: boolean): void {
  node.selected = selected;
  for (const child of node.children) {
    setNodeSelected(child, selected);
  }
}

/**
 * Count total selected leaf nodes in the tree.
 */
export function countSelected(node: TreeNode): number {
  if (node.children.length === 0) {
    return node.selected ? 1 : 0;
  }
  let total = 0;
  for (const child of node.children) {
    total += countSelected(child);
  }
  return total;
}

/**
 * Count total leaf nodes in the tree.
 */
export function countTotal(node: TreeNode): number {
  if (node.children.length === 0) return 1;
  let total = 0;
  for (const child of node.children) {
    total += countTotal(child);
  }
  return total;
}

/**
 * Get all excluded (unselected) leaf nodes.
 */
export function getExcludedEntries(node: TreeNode): TreeNode[] {
  if (node.children.length === 0) {
    return node.selected ? [] : [node];
  }
  const excluded: TreeNode[] = [];
  for (const child of node.children) {
    excluded.push(...getExcludedEntries(child));
  }
  return excluded;
}

/**
 * Format byte size to human-readable string.
 */
export function formatSize(bytes: number | undefined): string {
  if (bytes === undefined || bytes === null) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}
