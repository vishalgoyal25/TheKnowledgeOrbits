"use client";

/**
 * SSEProvider.tsx — the shared memory from the Uber analogy.
 *
 * Runs useResearchSSE ONCE and shares its output via React context so every
 * child component (ResearchGraph, ResearchReport, status bar, etc.) reads from
 * the SAME single SSE connection — no duplicate connections, no prop drilling.
 *
 * Also owns the dynamic() import of ResearchGraph (ssr:false boundary) because
 * SSEProvider is already client-only and is the natural place to gate the
 * browser-only React Flow dependency [Risk #43].
 *
 * Usage:
 *   <SSEProvider sessionId={sessionId}>
 *     <ResearchGraph />      ← reads agentStatuses from context
 *     <ResearchReport />     ← reads reportTokens from context
 *   </SSEProvider>
 *
 *   // In any child:
 *   const { agentStatuses, reportTokens, isComplete } = useSSEContext();
 */

import { createContext, useContext, useState, type ReactNode } from "react";
import dynamic from "next/dynamic";
import {
  useResearchSSE,
  type SSEState,
  type AgentStatus,
} from "@/lib/hooks/use-research-sse";

// ── Dynamic ResearchGraph import (ssr:false) ──────────────────────────────────
// React Flow uses browser-only APIs. Without ssr:false Next.js crashes during
// server render. The dynamic() call lives here — SSEProvider is already
// client-only ("use client"), making it the correct SSR boundary [Risk #43].
export const ResearchGraphDynamic = dynamic(() => import("./ResearchGraph"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-[960px] rounded-xl border border-gray-100 bg-gray-50 animate-pulse" />
  ),
});

// ── Context shape ─────────────────────────────────────────────────────────────

interface SSEContextValue extends SSEState {
  sessionId: string | null;
  // Actions — called by ResearchInput on submit / cancel
  startSession: (id: string) => void;
  clearSession: () => void;
}

const SSEContext = createContext<SSEContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────────────────────────

interface SSEProviderProps {
  children: ReactNode;
}

export function SSEProvider({ children }: SSEProviderProps) {
  // sessionId is managed here so ResearchInput can trigger the SSE connection
  // by calling startSession(id) after the POST /query/ returns.
  const [sessionId, setSessionId] = useState<string | null>(null);

  // One hook call — one SSE connection — shared across ALL children.
  const sseState = useResearchSSE(sessionId);

  function startSession(id: string) {
    setSessionId(id);
  }

  function clearSession() {
    setSessionId(null);
  }

  return (
    <SSEContext.Provider
      value={{
        ...sseState,
        sessionId,
        startSession,
        clearSession,
      }}
    >
      {children}
    </SSEContext.Provider>
  );
}

// ── Consumer hook ─────────────────────────────────────────────────────────────

/**
 * useSSEContext — read SSE state from any child of SSEProvider.
 *
 * Throws if called outside of SSEProvider (dev-time guardrail).
 */
export function useSSEContext(): SSEContextValue {
  const ctx = useContext(SSEContext);
  if (ctx === null) {
    throw new Error("useSSEContext must be used inside <SSEProvider>");
  }
  return ctx;
}

// Re-export AgentStatus so consumers don't need a separate import.
export type { AgentStatus };
