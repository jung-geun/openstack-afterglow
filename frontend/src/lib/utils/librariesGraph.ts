import type { LibraryConfig, GraphNode, GraphEdge } from '$lib/types/libraries';

export interface GraphLayout {
  nodes: GraphNode[];
  edges: GraphEdge[];
  width: number;
  height: number;
  nodeW: number;
  nodeH: number;
}

export const GRAPH_NODE_W = 130;
export const GRAPH_NODE_H = 36;
const H_GAP = 60;
const V_GAP = 20;
const PAD_X = 20;
const PAD_Y = 20;

export function buildLibraryGraph(
  libraries: LibraryConfig[],
  getStatus: (lib: LibraryConfig) => string,
): GraphLayout {
  if (libraries.length === 0) {
    return { nodes: [], edges: [], width: 0, height: 0, nodeW: GRAPH_NODE_W, nodeH: GRAPH_NODE_H };
  }

  const levels: Record<string, number> = {};
  function calcLevel(id: string): number {
    if (levels[id] !== undefined) return levels[id];
    const lib = libraries.find(l => l.id === id);
    if (!lib || lib.depends_on.length === 0) {
      levels[id] = 0;
      return 0;
    }
    levels[id] = Math.max(...lib.depends_on.map(dep => calcLevel(dep) + 1));
    return levels[id];
  }
  libraries.forEach(l => calcLevel(l.id));

  const byLevel: Record<number, LibraryConfig[]> = {};
  libraries.forEach(l => {
    const lv = levels[l.id] ?? 0;
    if (!byLevel[lv]) byLevel[lv] = [];
    byLevel[lv].push(l);
  });

  const maxLv = Math.max(...Object.keys(byLevel).map(Number));

  const nodes: GraphNode[] = [];
  for (let lv = 0; lv <= maxLv; lv++) {
    const group = byLevel[lv] ?? [];
    group.forEach((lib, idx) => {
      nodes.push({
        id: lib.id,
        name: lib.name,
        level: lv,
        posX: PAD_X + lv * (GRAPH_NODE_W + H_GAP),
        posY: PAD_Y + idx * (GRAPH_NODE_H + V_GAP),
        status: getStatus(lib),
      });
    });
  }

  const edges: GraphEdge[] = [];
  libraries.forEach(lib => {
    lib.depends_on.forEach(dep => {
      edges.push({ from: dep, to: lib.id });
    });
  });

  const width = PAD_X * 2 + (maxLv + 1) * (GRAPH_NODE_W + H_GAP) - H_GAP;
  const maxNodesPerLevel = Math.max(...Object.values(byLevel).map(g => g.length));
  const height = PAD_Y * 2 + maxNodesPerLevel * (GRAPH_NODE_H + V_GAP) - V_GAP;

  return { nodes, edges, width, height, nodeW: GRAPH_NODE_W, nodeH: GRAPH_NODE_H };
}

export function nodeColor(status: string): string {
  const map: Record<string, string> = {
    ready: '#16a34a',
    building: '#2563eb',
    failed: '#dc2626',
    none: '#4b5563',
  };
  return map[status] ?? '#4b5563';
}
