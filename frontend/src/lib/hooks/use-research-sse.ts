/**
 * frontend/src/lib/hooks/use-research-sse.ts
 * ─────────────────────────────────────────────
 * Manages the live SSE connection from the browser to the background worker.
 *
 * Architecture: worker → Redis pub/sub → Django stream view → EventSource → this hook
 * CRITICAL: EventSource opens to BACKEND_SSE_BASE_URL (Render) directly.
 *           Never route SSE through Vercel — it buffers streaming responses.
 *
 * Production risks addressed:
 *   [Risk #12] buildSSEUrl() uses NEXT_PUBLIC_RENDER_BACKEND_URL, never Vercel proxy
 *   [Risk #10] Auto-reconnects on drop: max 3 attempts, exponential backoff (3s/6s/12s)
 *   [Risk #11] report_token events batched every 50ms — prevents re-render storm
 *              (backend streams ~80-char chunks; without batching = hundreds of re-renders/s)
 *   [zombie]  Tab visibility: close EventSource on tab hide, reconnect on show
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  buildSSEUrl,
  SSE_MAX_RECONNECT_ATTEMPTS,
  SSE_RECONNECT_DELAY_MS,
} from "@/lib/api/research-agent";
import type {
  NodeStartedData,
  NodeCompletedData,
  ReportTokenData,
  WorkflowFailedData,
} from "@/types/research_agent";

// ── Types ─────────────────────────────────────────────────────────────────────

export type AgentStatus = "pending" | "running" | "completed" | "failed";

export interface SSEState {
  isConnected: boolean;
  agentStatuses: Record<string, AgentStatus>;
  reportTokens: string;
  executiveSummary: string;
  isComplete: boolean;
  error: string | null;
}

const INITIAL_STATE: SSEState = {
  isConnected: false,
  agentStatuses: {},
  reportTokens: "",
  executiveSummary: "",
  isComplete: false,
  error: null,
};

// Batch report_token events into one setState every 50ms.
// Without this, a fast stream fires hundreds of re-renders/second.
const TOKEN_FLUSH_MS = 50;

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useResearchSSE(sessionId: string | null): SSEState {
  const [state, setState] = useState<SSEState>(INITIAL_STATE);

  // Refs hold mutable state that must NOT trigger re-renders.
  const esRef = useRef<EventSource | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const summaryBufRef = useRef(""); // batched executive_summary tokens
  const reportBufRef = useRef(""); // batched full_report tokens
  const isCompleteRef = useRef(false); // prevents reconnect after terminal state
  const hasTerminatedRef = useRef(false); // failed or cancelled

  // Flush accumulated token buffers into state in one batch.
  // useCallback with [] because it only reads/writes refs — always stable.
  const flushTokenBuffer = useCallback(() => {
    const summary = summaryBufRef.current;
    const report = reportBufRef.current;
    summaryBufRef.current = "";
    reportBufRef.current = "";
    flushTimerRef.current = null;

    if (summary || report) {
      setState((prev) => ({
        ...prev,
        executiveSummary: summary
          ? prev.executiveSummary + summary
          : prev.executiveSummary,
        reportTokens: report ? prev.reportTokens + report : prev.reportTokens,
      }));
    }
  }, []);

  useEffect(() => {
    if (!sessionId) {
      setState(INITIAL_STATE);
      isCompleteRef.current = false;
      hasTerminatedRef.current = false;
      return;
    }

    reconnectCountRef.current = 0;

    // openConnection is defined inside the effect so it closes over the
    // correct sessionId and can safely schedule itself for reconnection.
    function openConnection() {
      esRef.current?.close();

      const es = new EventSource(buildSSEUrl(sessionId!));
      esRef.current = es;

      // ── Connection open ──────────────────────────────────────────────────
      es.onopen = () => {
        reconnectCountRef.current = 0;
        setState((prev) => ({ ...prev, isConnected: true, error: null }));
      };

      // ── Per-node events (drive React Flow graph colours) ─────────────────
      es.addEventListener("node_started", (e: MessageEvent) => {
        try {
          const data: NodeStartedData = JSON.parse(e.data);
          setState((prev) => {
            const newStatuses = {
              ...prev.agentStatuses,
              [data.agent]: "running" as AgentStatus,
            };
            // Re-plan: report_generator restarting with existing tokens → clear stale report.
            // Without this, 2nd-run tokens append to 1st-run output → two reports on screen.
            if (
              data.agent === "report_generator" &&
              prev.reportTokens.length > 0
            ) {
              summaryBufRef.current = "";
              reportBufRef.current = "";
              return {
                ...prev,
                agentStatuses: newStatuses,
                reportTokens: "",
                executiveSummary: "",
              };
            }
            return { ...prev, agentStatuses: newStatuses };
          });
        } catch {
          /* skip malformed frame */
        }
      });

      es.addEventListener("node_completed", (e: MessageEvent) => {
        try {
          const data: NodeCompletedData = JSON.parse(e.data);
          const status: AgentStatus =
            data.status === "failed" ? "failed" : "completed";
          setState((prev) => ({
            ...prev,
            agentStatuses: { ...prev.agentStatuses, [data.agent]: status },
          }));
        } catch {
          /* skip malformed frame */
        }
      });

      // ── Streaming report tokens (batched — Risk #11) ─────────────────────
      es.addEventListener("report_token", (e: MessageEvent) => {
        try {
          const data: ReportTokenData = JSON.parse(e.data);
          if (data.phase === "summary") {
            summaryBufRef.current += data.token;
          } else {
            reportBufRef.current += data.token;
          }
          // Schedule one flush if none pending — coalesces burst of tokens.
          if (flushTimerRef.current === null) {
            flushTimerRef.current = setTimeout(
              flushTokenBuffer,
              TOKEN_FLUSH_MS,
            );
          }
        } catch {
          /* skip malformed frame */
        }
      });

      // ── Terminal: completed ───────────────────────────────────────────────
      es.addEventListener("workflow_completed", () => {
        // Flush immediately so the UI shows the complete report, not a partial.
        if (flushTimerRef.current !== null) {
          clearTimeout(flushTimerRef.current);
          flushTokenBuffer();
        }
        isCompleteRef.current = true;
        setState((prev) => ({ ...prev, isConnected: false, isComplete: true }));
        es.close();
      });

      // ── Terminal: failed ─────────────────────────────────────────────────
      es.addEventListener("workflow_failed", (e: MessageEvent) => {
        hasTerminatedRef.current = true;
        try {
          const data: WorkflowFailedData = JSON.parse(e.data);
          setState((prev) => ({
            ...prev,
            isConnected: false,
            error: data.error ?? "Research failed unexpectedly.",
          }));
        } catch {
          setState((prev) => ({
            ...prev,
            isConnected: false,
            error: "Research failed unexpectedly.",
          }));
        }
        es.close();
      });

      // ── Terminal: cancelled ──────────────────────────────────────────────
      es.addEventListener("workflow_cancelled", () => {
        hasTerminatedRef.current = true;
        setState((prev) => ({
          ...prev,
          isConnected: false,
          error: "Research was cancelled.",
        }));
        es.close();
      });

      // heartbeat: backend emits ": heartbeat\n\n" (SSE comment).
      // The browser EventSource API processes comments silently — no listener needed.
      // They exist purely to prevent Render/Vercel proxy from closing the idle connection.

      // ── Connection error / drop → reconnect with backoff ─────────────────
      es.onerror = () => {
        setState((prev) => ({ ...prev, isConnected: false }));
        es.close();

        // Do not reconnect after a clean terminal state.
        if (isCompleteRef.current || hasTerminatedRef.current) return;

        if (reconnectCountRef.current >= SSE_MAX_RECONNECT_ATTEMPTS) {
          setState((prev) => ({
            ...prev,
            error: "Connection lost. Please refresh to resume.",
          }));
          return;
        }

        // Exponential backoff: 3s → 6s → 12s
        const delay =
          SSE_RECONNECT_DELAY_MS * Math.pow(2, reconnectCountRef.current);
        reconnectCountRef.current += 1;
        reconnectTimerRef.current = setTimeout(openConnection, delay);
      };
    }

    openConnection();

    // ── Tab visibility: kill zombie connections (Risk zombie) ────────────────
    // When the tab is hidden the browser may throttle or close the EventSource.
    // We close proactively and reopen when the tab comes back into focus.
    function handleVisibilityChange() {
      if (document.hidden) {
        esRef.current?.close();
        setState((prev) => ({ ...prev, isConnected: false }));
      } else if (!isCompleteRef.current && !hasTerminatedRef.current) {
        openConnection();
      }
    }
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      esRef.current?.close();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (reconnectTimerRef.current !== null)
        clearTimeout(reconnectTimerRef.current);
      if (flushTimerRef.current !== null) {
        clearTimeout(flushTimerRef.current);
        flushTokenBuffer(); // don't lose buffered tokens on unmount
      }
    };
  }, [sessionId, flushTokenBuffer]);

  return state;
}
