import { useMemo } from 'react';
import ReactFlow, { Background, Controls, MarkerType, type Edge, type Node, type NodeMouseHandler } from 'reactflow';
import 'reactflow/dist/style.css';
import type { MissionGraphData, MissionNodeStatus } from '../types';

interface MissionGraphProps {
  graph: MissionGraphData;
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string) => void;
}

const nodeColors: Record<MissionNodeStatus, { border: string; badge: string; text: string }> = {
  pending: { border: '#334155', badge: '#64748b', text: '#94a3b8' },
  running: { border: '#14b8a6', badge: '#14b8a6', text: '#5eead4' },
  completed: { border: '#22c55e', badge: '#22c55e', text: '#86efac' },
  failed: { border: '#ef4444', badge: '#ef4444', text: '#fca5a5' },
  blocked: { border: '#f59e0b', badge: '#f59e0b', text: '#fcd34d' },
};

const computeNodePosition = (index: number): { x: number; y: number } => {
  const column = index % 4;
  const row = Math.floor(index / 4);
  return {
    x: 120 + column * 220,
    y: 80 + row * 160,
  };
};

export function MissionGraph({ graph, selectedNodeId, onNodeSelect }: MissionGraphProps) {
  const nodes = useMemo<Node[]>(
    () =>
      graph.nodes.map((node, index) => {
        const colors = nodeColors[node.status];
        const isSelected = node.id === selectedNodeId;
        const position = computeNodePosition(index);

        return {
          id: node.id,
          position,
          data: {
            label: (
              <div className="min-w-32 text-left">
                <p className="text-xs font-semibold text-slate-100">{node.label}</p>
                <p className="mt-1 text-[11px] text-slate-400">{node.type}</p>
                <p className="mt-1 text-[11px] uppercase tracking-wide" style={{ color: colors.text }}>
                  {node.status}
                </p>
                <div className="mt-2 h-1.5 w-full rounded-full" style={{ backgroundColor: colors.badge }} />
              </div>
            ),
          },
          style: {
            border: `1px solid ${colors.border}`,
            borderRadius: 10,
            background: '#0b1220',
            color: '#e2e8f0',
            padding: 8,
            boxShadow: isSelected ? `0 0 0 2px ${colors.badge}` : node.isActive ? '0 0 0 1px #14b8a6' : 'none',
          },
        };
      }),
    [graph.nodes, selectedNodeId],
  );

  const edges = useMemo<Edge[]>(
    () =>
      graph.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label ?? edge.condition ?? undefined,
        markerEnd: { type: MarkerType.ArrowClosed, color: '#475569' },
        style: { stroke: '#475569', strokeWidth: 1.2 },
        labelStyle: { fill: '#94a3b8', fontSize: 11 },
      })),
    [graph.edges],
  );

  const onNodeClick: NodeMouseHandler = (_, node) => onNodeSelect?.(node.id);

  return (
    <div className="h-[440px] rounded-lg border border-slate-800 bg-slate-950">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesConnectable={false} nodesDraggable={false} onNodeClick={onNodeClick}>
        <Background color="#1e293b" gap={24} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
