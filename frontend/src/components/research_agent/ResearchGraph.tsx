"use client";

/**
 * ResearchGraph.tsx — the live map: all 8 agent nodes laid out as a vertical pipeline.
 *
 * IMPORTANT: This component uses browser-only React Flow APIs.
 * It must be imported with dynamic() + ssr:false by its parent (SSEProvider / page.tsx).
 * The component itself does NOT self-wrap — the parent owns the dynamic boundary.
 *
 * Production risks addressed:
 *   [Risk #35] Node positions are fixed constants defined OUTSIDE the component.
 *              Only node `data` (status) updates on each SSE event — positions
 *              never recalculate, so the graph never jumps or re-layouts.
 *   [Risk #43] Caller must use dynamic(import, {ssr:false}) — React Flow uses
 *              browser-only APIs that crash Next.js SSR if imported normally.
 */

import { useEffect } from "react";
import type { ComponentType } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  type Node,
  type Edge,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import AgentNode, { type AgentNodeData } from "./AgentNode";
import type { AgentStatus } from "@/lib/hooks/use-research-sse";
import { AGENT_NAMES } from "@/lib/api/research-agent";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ResearchGraphProps {
  agentStatuses: Record<string, AgentStatus>;
}

// ── Constants (all defined OUTSIDE the component) ─────────────────────────────
// React Flow requirement: nodeTypes defined outside = stable reference = no warnings.

// Cast required: NodeTypes expects ComponentType<NodeProps> (base generic),
// but AgentNode is typed for the specific NodeProps<AgentNodeType>.
// This is the standard React Flow v12 community pattern for typed custom nodes.
const NODE_TYPES: NodeTypes = {
  agentNode: AgentNode as ComponentType<NodeProps>,
};

// Human-readable labels for each agent (matches AGENT_NAMES order).
const AGENT_LABELS: Record<string, string> = {
  supervisor: "Supervisor",
  planner: "Planner",
  search: "Web Search",
  research: "Research",
  verification: "Verification",
  summary_generator: "Summary",
  report_generator: "Report",
  reflection: "Reflection",
};

// Fixed vertical layout — 8 nodes, 110px apart.
// NEVER recalculated. Only data.status changes on SSE events [Risk #35].
const INITIAL_NODES: Node<AgentNodeData>[] = AGENT_NAMES.map((name, index) => ({
  id: name,
  type: "agentNode",
  position: { x: 0, y: index * 110 },
  data: {
    label: AGENT_LABELS[name] ?? name,
    status: "pending" as AgentStatus,
  },
  draggable: false,
}));

// Sequential pipeline edges: supervisor→planner→search→...→reflection
const PIPELINE_EDGES: Edge[] = AGENT_NAMES.slice(0, -1).map((name, i) => ({
  id: `${name}->${AGENT_NAMES[i + 1]}`,
  source: name,
  target: AGENT_NAMES[i + 1],
  style: { stroke: "#cbd5e1", strokeWidth: 1.5 },
}));

// Conditional edge: reflection can send workflow back to planner for re-planning.
const CONDITIONAL_EDGE: Edge = {
  id: "reflection->planner",
  source: "reflection",
  target: "planner",
  type: "smoothstep",
  style: { stroke: "#94a3b8", strokeDasharray: "5 4", strokeWidth: 1 },
  label: "re-plan",
  labelStyle: { fontSize: 9, fill: "#94a3b8" },
};

const EDGES: Edge[] = [...PIPELINE_EDGES, CONDITIONAL_EDGE];

// ── Component ─────────────────────────────────────────────────────────────────

export default function ResearchGraph({ agentStatuses }: ResearchGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(INITIAL_NODES);

  // When agentStatuses changes (from SSE events), update ONLY node data.
  // Positions are never touched — prevents layout jumping [Risk #35].
  useEffect(() => {
    setNodes((prev) =>
      prev.map((node) => {
        const incoming = agentStatuses[node.id] ?? "pending";
        // Skip re-render if status unchanged — avoids unnecessary node repaints.
        if (node.data.status === incoming) return node;
        return { ...node, data: { ...node.data, status: incoming } };
      }),
    );
  }, [agentStatuses, setNodes]);

  return (
    <div className="w-full h-[480px] sm:h-[560px] lg:h-[calc(100dvh-8rem)] rounded-xl border border-gray-100 bg-white shadow-sm overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={EDGES}
        nodeTypes={NODE_TYPES}
        onNodesChange={onNodesChange}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} size={1} color="#f1f5f9" />
        <Controls showInteractive={false} position="bottom-right" />
      </ReactFlow>
    </div>
  );
}
