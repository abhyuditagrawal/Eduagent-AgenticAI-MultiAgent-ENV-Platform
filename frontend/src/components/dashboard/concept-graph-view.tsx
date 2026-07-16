"use client";

import { useCallback, useEffect, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  Handle,
  Position,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";

interface GraphNode {
  id: string;
  name: string;
  chapter: string | null;
  difficulty: number;
  confidence: number;
  status: string;
}

interface GraphEdge {
  source: string;
  target: string;
  strength: number;
}

interface ConceptGraphViewProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const STATUS_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  mastered: { bg: "#dcfce7", border: "#22c55e", text: "#15803d" },
  proficient: { bg: "#dbeafe", border: "#3b82f6", text: "#1d4ed8" },
  developing: { bg: "#fed7aa", border: "#f97316", text: "#c2410c" },
  not_started: { bg: "#f3f4f6", border: "#9ca3af", text: "#4b5563" },
};

function ConceptNode({ data }: { data: { label: string; confidence: number; status: string; difficulty: number } }) {
  const colors = STATUS_COLORS[data.status] || STATUS_COLORS.not_started;
  const pct = Math.round(data.confidence * 100);

  return (
    <>
      <Handle type="target" position={Position.Top} className="!bg-gray-400 !w-2 !h-2" />
      <div
        className="px-3 py-2 rounded-lg shadow-sm border-2 min-w-[120px] text-center cursor-pointer transition-shadow hover:shadow-md"
        style={{
          backgroundColor: colors.bg,
          borderColor: colors.border,
          color: colors.text,
        }}
      >
        <div className="text-xs font-medium leading-tight">{data.label}</div>
        <div className="text-[10px] mt-0.5 opacity-75">{pct}%</div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-gray-400 !w-2 !h-2" />
    </>
  );
}

const nodeTypes = { concept: ConceptNode };

function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  direction = "TB"
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 50, ranksep: 80 });

  nodes.forEach((node) => {
    g.setNode(node.id, { width: 140, height: 50 });
  });

  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: pos.x - 70, y: pos.y - 25 },
    };
  });

  return { nodes: layoutedNodes, edges };
}

export function ConceptGraphView({ nodes: graphNodes, edges: graphEdges }: ConceptGraphViewProps) {
  const initialNodes: Node[] = useMemo(
    () =>
      graphNodes.map((n) => ({
        id: n.id,
        type: "concept",
        position: { x: 0, y: 0 },
        data: {
          label: n.name,
          confidence: n.confidence,
          status: n.status,
          difficulty: n.difficulty,
        },
      })),
    [graphNodes]
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      graphEdges.map((e, i) => {
        const sourceNode = graphNodes.find((n) => n.id === e.source);
        const targetNode = graphNodes.find((n) => n.id === e.target);
        const bothMastered =
          sourceNode?.status === "mastered" && targetNode?.status === "mastered";

        return {
          id: `e-${i}`,
          source: e.source,
          target: e.target,
          animated: !bothMastered,
          style: {
            stroke: bothMastered ? "#22c55e" : "#ef4444",
            strokeWidth: 2,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: bothMastered ? "#22c55e" : "#ef4444",
          },
        };
      }),
    [graphEdges, graphNodes]
  );

  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(
    () => getLayoutedElements(initialNodes, initialEdges),
    [initialNodes, initialEdges]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  useEffect(() => {
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [layoutedNodes, layoutedEdges, setNodes, setEdges]);

  if (graphNodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        No concepts found. Populate concepts for this subject first.
      </div>
    );
  }

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.3}
        maxZoom={2}
        attributionPosition="bottom-left"
      >
        <Background gap={16} size={1} />
        <Controls />
        <MiniMap
          nodeStrokeWidth={2}
          nodeColor={(n) => {
            const s = n.data?.status as string;
            return STATUS_COLORS[s]?.border || "#9ca3af";
          }}
          className="!bg-card"
        />
      </ReactFlow>

      {/* Legend */}
      <div className="absolute bottom-4 right-4 bg-card/90 backdrop-blur-sm border rounded-lg p-3 space-y-1.5">
        <p className="text-[10px] font-medium text-muted-foreground uppercase">Legend</p>
        {Object.entries(STATUS_COLORS).map(([status, colors]) => (
          <div key={status} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-sm border"
              style={{ backgroundColor: colors.bg, borderColor: colors.border }}
            />
            <span className="text-[10px] capitalize">{status.replace("_", " ")}</span>
          </div>
        ))}
        <div className="flex items-center gap-2 pt-1 border-t">
          <div className="w-6 h-0.5 bg-green-500" />
          <span className="text-[10px]">Both mastered</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-0.5 bg-red-500" />
          <span className="text-[10px]">Gap exists</span>
        </div>
      </div>
    </div>
  );
}
