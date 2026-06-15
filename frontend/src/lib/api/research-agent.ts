/**
 * frontend/src/lib/api/research-agent.ts
 * ─────────────────────────────────────────
 * API client + constants for the Research Agent engine.
 * Follows the project's src/lib/api/<feature>.ts convention (same as bookmarks.ts, daily-ca.ts).
 *
 * IMPORTANT: SSE (EventSource) is NOT handled here — it cannot use axios.
 * The SSE hook (use-research-sse.ts) opens EventSource directly to BACKEND_SSE_BASE_URL.
 * This file only exports the base URL constant + HTTP REST calls.
 */

import apiClient, { getErrorMessage } from "./client";
import type {
  QuerySubmitResponse,
  QueryStartedResponse,
  ResearchSession,
  ResearchReport,
  HistoryListItem,
} from "@/types/research_agent";

// ── Constants ─────────────────────────────────────────────────────────────────

// SSE EventSource must connect DIRECTLY to Render, never through Vercel.
// (Vercel buffers streaming responses, which breaks SSE.)
export const BACKEND_SSE_BASE_URL =
  process.env.NEXT_PUBLIC_RENDER_BACKEND_URL ?? "http://localhost:8000";

// All REST calls go through apiClient (which uses NEXT_PUBLIC_API_URL).
// Exported for use in components that display the raw URL or build links.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// Agent names in execution order — must match backend AgentName constants exactly.
export const AGENT_NAMES = [
  "supervisor",
  "planner",
  "search",
  "research",
  "verification",
  "summary_generator",
  "report_generator",
  "reflection",
] as const;

export type AgentName = (typeof AGENT_NAMES)[number];

// Confidence score thresholds — drive ConfidenceBadge colour coding.
export const CONFIDENCE_HIGH = 0.8;
export const CONFIDENCE_MED = 0.6;

// SSE reconnect config — used by use-research-sse.ts.
export const SSE_MAX_RECONNECT_ATTEMPTS = 3;
export const SSE_RECONNECT_DELAY_MS = 3000;

// Public daily query limit — mirrors backend PUBLIC_DAILY_LIMIT in constants.py.
export const PUBLIC_DAILY_LIMIT = 3;

// ── URL Helpers ───────────────────────────────────────────────────────────────

/** Build the SSE EventSource URL for a session. Used by use-research-sse.ts. */
export function buildSSEUrl(sessionId: string): string {
  return `${BACKEND_SSE_BASE_URL}/api/v1/research/stream/${sessionId}/`;
}

/** Build the export download URL. Browser navigates here directly (no fetch). */
export function buildExportUrl(
  sessionId: string,
  format: "pdf" | "md",
): string {
  return `${API_BASE_URL}/research/export/${sessionId}/?format=${format}`;
}

// ── API Functions ─────────────────────────────────────────────────────────────

/**
 * POST /api/v1/research/query/
 *
 * Two possible success paths from the backend:
 *   202 → new session queued   → {session_id, status, stream_url}
 *   200 → cache hit (identical query already answered) → {cached: true, status, report}
 *
 * 429 → daily rate limit hit → throws with the backend's user-facing message.
 */
export async function submitResearchQuery(
  query: string,
): Promise<QuerySubmitResponse> {
  try {
    const response = await apiClient.post("/research/query/", { query });
    const data = response.data;

    if (data.cached === true) {
      return data as QuerySubmitResponse; // QueryCachedResponse
    }

    // Non-cached: backend returns {session_id, status, stream_url} — add cached: false.
    return { ...data, cached: false } as QueryStartedResponse;
  } catch (error: unknown) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * GET /api/v1/research/history/<session_id>/
 *
 * Returns the session row + its report (if completed).
 * Auth required — IsAuthenticated on backend. apiClient handles the Bearer token.
 */
export async function getSessionDetail(
  sessionId: string,
): Promise<ResearchSession & { report: ResearchReport | null }> {
  try {
    const response = await apiClient.get(`/research/history/${sessionId}/`);
    return response.data;
  } catch (error: unknown) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * GET /api/v1/research/history/?page=N
 *
 * Paginated list of the authenticated user's past sessions.
 * Returns DRF paginated shape: {count, next, previous, results}.
 */
export async function getResearchHistory(page = 1): Promise<{
  count: number;
  next: string | null;
  previous: string | null;
  results: HistoryListItem[];
}> {
  try {
    const response = await apiClient.get("/research/history/", {
      params: { page },
    });
    return response.data;
  } catch (error: unknown) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * POST /api/v1/research/cancel/<session_id>/
 *
 * Sets the Redis cancel flag so agents stop wasting API budget.
 * Also called via navigator.sendBeacon on tab close (page.tsx cleanup).
 */
export async function cancelSession(sessionId: string): Promise<void> {
  try {
    await apiClient.post(`/research/cancel/${sessionId}/`);
  } catch (error: unknown) {
    throw new Error(getErrorMessage(error));
  }
}
