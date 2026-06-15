/**
 * frontend/src/types/research_agent.ts
 * ──────────────────────────────────────
 * TypeScript type definitions for Research Agent.
 * Mirrors Django serializer output + SSE event payloads exactly.
 * All shapes verified against backend Phase 1-9 implementation.
 */

// ── Session ───────────────────────────────────────────────────────────────────
export type SessionStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface ResearchSession {
  id: string;
  query: string;
  status: SessionStatus;
  created_at: string;
  completed_at: string | null;
  langfuse_trace_id: string | null;
}

// ── Report ────────────────────────────────────────────────────────────────────
export interface Source {
  url: string;
  title: string;
  credibility_score: number | null; // null when search tool didn't score it
}

export interface ResearchReport {
  session_id: string;
  executive_summary: string;
  full_report: string;
  sources: Source[];
  confidence_score: number | null; // null until DeepEval evaluation completes
  word_count: number;
  created_at: string;
}

// ── SSE Event Types ───────────────────────────────────────────────────────────
// Names must match backend SSEEvent class in constants.py exactly.
export type SSEEventType =
  | "workflow_started"
  | "node_started"
  | "node_completed"
  | "report_token"
  | "workflow_completed"
  | "workflow_failed"
  | "workflow_cancelled"
  | "heartbeat";

export interface SSEEvent {
  event: SSEEventType;
  data: SSEEventData;
}

export type SSEEventData =
  | WorkflowStartedData
  | NodeStartedData
  | NodeCompletedData
  | ReportTokenData
  | WorkflowCompletedData
  | WorkflowFailedData
  | WorkflowCancelledData
  | HeartbeatData;

// orchestrator.py: emit(WORKFLOW_STARTED, {"query": ..., "status": "running"})
export interface WorkflowStartedData {
  query: string;
  status: "running";
}

// base_agent.py: emit(NODE_STARTED, {"agent": self.agent_name})
export interface NodeStartedData {
  agent: string;
}

// base_agent.py: emit(NODE_COMPLETED, {"agent": ..., "duration_ms": ..., "tokens": ...})
// on failure: emit(NODE_COMPLETED, {"agent": ..., "status": "failed"})
export interface NodeCompletedData {
  agent: string;
  duration_ms?: number;
  tokens?: number;
  status?: "failed";
}

// report_generator.py / summary_generator.py: emit(REPORT_TOKEN, {"token": ..., "phase": ...})
export interface ReportTokenData {
  token: string;
  phase: "summary" | "full_report";
}

// orchestrator.py: emit(WORKFLOW_COMPLETED, {"word_count": ..., "total_tokens": ..., "reflection_score": ...})
export interface WorkflowCompletedData {
  word_count: number;
  total_tokens: number;
  reflection_score: number | null;
}

// orchestrator.py: emit(WORKFLOW_FAILED, {"error": "internal_error"})
export interface WorkflowFailedData {
  error: string;
}

// orchestrator.py: emit(WORKFLOW_CANCELLED, {"reason": ...})
export interface WorkflowCancelledData {
  reason: string;
}

// sse_service.py: yields ": heartbeat\n\n" (SSE comment, no data frame)
export interface HeartbeatData {
  timestamp?: string;
}

// ── API Response Shapes ───────────────────────────────────────────────────────

// POST /api/v1/research/query/ — non-cached path (202)
// query_view.py _payload(): {session_id, status, stream_url}
export interface QueryStartedResponse {
  session_id: string;
  status: SessionStatus;
  stream_url: string;
  cached: false;
}

// POST /api/v1/research/query/ — cache hit path (200)
// query_view.py: {cached: true, status: "completed", report: {...}}
export interface QueryCachedResponse {
  cached: true;
  status: "completed";
  report: Omit<ResearchReport, "session_id" | "created_at">;
}

// Union — what submitResearchQuery() actually returns (either branch)
export type QuerySubmitResponse = QueryStartedResponse | QueryCachedResponse;

// HistoryListSerializer fields: id, query (truncated 80), status,
// confidence_score (from related report), created_at, completed_at
export interface HistoryListItem {
  id: string;
  query: string;
  status: SessionStatus;
  confidence_score: number | null;
  created_at: string;
  completed_at: string | null;
}
