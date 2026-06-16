"use client";

/**
 * AgentNode.tsx — one card in the React Flow pipeline graph.
 *
 * In the Uber analogy: this is ONE dot on the live map (one agent's status card).
 * It is 100% visual — no logic, no API calls. All data flows in from ResearchGraph
 * (which gets it from SSEProvider → useResearchSSE).
 *
 * Status drives everything: border colour, background, icon, pulse animation.
 */

import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { CheckCircle2, XCircle, Loader2, Clock } from "lucide-react";
import type { AgentStatus } from "@/lib/hooks/use-research-sse";

// ── Data shape ────────────────────────────────────────────────────────────────
export interface AgentNodeData extends Record<string, unknown> {
  label: string;
  status: AgentStatus;
  tokens?: number;
  duration_ms?: number;
}

// ── Full React Flow v12 node type ─────────────────────────────────────────────
// NodeProps<T> in v12 requires T to extend Node<Data, Type>, NOT just the data.
// ResearchGraph and NodeTypes registry both import this type.
export type AgentNodeType = Node<AgentNodeData, "agentNode">;

// ── Status → visual style mapping ─────────────────────────────────────────────
const STATUS_STYLES: Record<
  AgentStatus,
  {
    border: string;
    bg: string;
    text: string;
  }
> = {
  pending: {
    border: "border-gray-200",
    bg: "bg-gray-50",
    text: "text-gray-500",
  },
  running: {
    border: "border-blue-400",
    bg: "bg-blue-50",
    text: "text-blue-700",
  },
  completed: {
    border: "border-green-400",
    bg: "bg-green-50",
    text: "text-green-700",
  },
  failed: { border: "border-red-400", bg: "bg-red-50", text: "text-red-700" },
};

// ── Status → icon ─────────────────────────────────────────────────────────────
function StatusIcon({ status }: { status: AgentStatus }) {
  switch (status) {
    case "running":
      return (
        <Loader2 className="w-4 h-4 text-blue-500 animate-spin flex-shrink-0" />
      );
    case "completed":
      return <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />;
    case "failed":
      return <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />;
    default:
      return <Clock className="w-4 h-4 text-gray-400 flex-shrink-0" />;
  }
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function AgentNode({ data }: NodeProps<AgentNodeType>) {
  const { label, status, tokens, duration_ms } = data;
  const styles = STATUS_STYLES[status as AgentStatus] ?? STATUS_STYLES.pending;

  return (
    <div
      className={[
        "relative w-48 rounded-2xl border-2 px-4 py-3.5 shadow-sm",
        "transition-all duration-300",
        styles.border,
        styles.bg,
        status === "running" ? "shadow-blue-200 shadow-md" : "",
      ].join(" ")}
    >
      {/* React Flow edge connection point — receives edge from the node above */}
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-gray-300 !w-2 !h-2 !border-0"
      />

      {/* Pulse ring — only while running (the "thinking" indicator) */}
      {status === "running" && (
        <span className="absolute inset-0 rounded-2xl animate-ping border-2 border-blue-500 opacity-60 pointer-events-none" />
      )}

      {/* Agent label + status icon */}
      <div className="flex items-center gap-1.5">
        <StatusIcon status={status} />
        <span
          className={`text-base font-semibold tracking-wide truncate ${styles.text}`}
        >
          {label}
        </span>
      </div>

      {/* Token + duration badge — only visible after completion */}
      {status === "completed" && (tokens != null || duration_ms != null) && (
        <div className="mt-1.5 flex items-center gap-2 text-[10px] text-gray-400 leading-none">
          {tokens != null && <span>{tokens.toLocaleString()} tok</span>}
          {duration_ms != null && (
            <span>{(duration_ms / 1000).toFixed(1)}s</span>
          )}
        </div>
      )}

      {/* React Flow edge connection point — sends edge to the node below */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-gray-300 !w-2 !h-2 !border-0"
      />
    </div>
  );
}
