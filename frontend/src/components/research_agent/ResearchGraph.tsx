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

import { useEffect, useMemo } from "react";
import type { ComponentType } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
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
  position: { x: 0, y: index * 135 },
  data: {
    label: AGENT_LABELS[name] ?? name,
    status: "pending" as AgentStatus,
  },
  draggable: false,
}));

// Edge palette.
const EDGE_GRAY = "#cbd5e1"; // pending / upcoming
const EDGE_GREEN = "#22c55e"; // completed transition
const EDGE_BLUE = "#3b82f6"; // active (in-progress) transition
const EDGE_RED = "#ef4444"; // failed target

const isDone = (s: AgentStatus) => s === "completed" || s === "failed";

/**
 * Build edges IN SYNC with node statuses so the connectors tell the same story
 * as the nodes:
 *   • upcoming        → thin gray, light arrow
 *   • in-progress     → glowing BLUE dashed arrow, animated (dashes flow downward)
 *   • completed       → solid GREEN arrow
 *   • failed target   → solid RED arrow
 * When the whole run is done, every pipeline edge is a solid green down-arrow.
 */
function buildEdges(agentStatuses: Record<string, AgentStatus>): Edge[] {
  const statusOf = (name: string): AgentStatus =>
    agentStatuses[name] ?? "pending";

  const pipeline: Edge[] = AGENT_NAMES.slice(0, -1).map((name, i) => {
    const target = AGENT_NAMES[i + 1];
    const s = statusOf(name);
    const t = statusOf(target);

    const active = isDone(s) && t === "running"; // the live transition
    const done = isDone(s) && isDone(t);

    let color = EDGE_GRAY;
    let width = 1.5;
    let animated = false;
    let dashed = false;
    let glow = false;

    if (active) {
      color = EDGE_BLUE;
      width = 2.5;
      animated = true; // React Flow flowing dashes → moves source→target (down)
      dashed = true;
      glow = true;
    } else if (done) {
      color = t === "failed" ? EDGE_RED : EDGE_GREEN;
      width = 2.5;
    }

    return {
      id: `${name}->${target}`,
      source: name,
      target,
      animated,
      style: {
        stroke: color,
        strokeWidth: width,
        strokeDasharray: dashed ? "6 4" : undefined,
        filter: glow ? `drop-shadow(0 0 5px ${EDGE_BLUE}aa)` : undefined,
      },
      markerEnd: { type: MarkerType.ArrowClosed, color, width: 20, height: 20 },
    };
  });

  // Conditional re-plan back-edge: glows only while a re-plan is actually running
  // (reflection done → planner running again); otherwise a subtle dashed hint.
  const replanActive =
    isDone(statusOf("reflection")) && statusOf("planner") === "running";
  const conditional: Edge = {
    id: "reflection->planner",
    source: "reflection",
    target: "planner",
    type: "smoothstep",
    animated: replanActive,
    style: {
      stroke: replanActive ? EDGE_BLUE : "#94a3b8",
      strokeDasharray: "5 4",
      strokeWidth: replanActive ? 2 : 1,
      filter: replanActive ? `drop-shadow(0 0 5px ${EDGE_BLUE}aa)` : undefined,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: replanActive ? EDGE_BLUE : "#94a3b8",
    },
    label: "re-plan",
    labelStyle: { fontSize: 9, fill: "#94a3b8" },
  };

  return [...pipeline, conditional];
}

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

  // Edges are derived from the SAME agentStatuses as the nodes → always in sync.
  const edges = useMemo(() => buildEdges(agentStatuses), [agentStatuses]);

  return (
    <div className="w-full h-[480px] sm:h-[560px] lg:h-[calc(100dvh-8rem)] rounded-xl border border-gray-100 bg-white shadow-sm overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
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
