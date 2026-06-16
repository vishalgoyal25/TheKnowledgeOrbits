"use client";

import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  FlaskConical,
  Loader2,
  WifiOff,
  ServerCrash,
  History,
} from "lucide-react";
import { useAuth } from "@/lib/hooks/use-auth";
import {
  useSSEContext,
  ResearchGraphDynamic,
} from "@/components/research_agent/SSEProvider";
import ResearchInput from "@/components/research_agent/ResearchInput";
import ResearchReport from "@/components/research_agent/ResearchReport";
import { getSessionDetail, AGENT_NAMES } from "@/lib/api/research-agent";
import type {
  ResearchReport as ResearchReportType,
  Source,
} from "@/types/research_agent";

const COLD_START_MS = 5000; // show "warming up" if no heartbeat within 5s of connect

const EXAMPLES = [
  "Panchayati Raj system",
  "Article 370 implications",
  "Green Revolution impact",
];

export default function ResearchAgentPage() {
  // Read ?q= param set by HomepageWidget; initialize pendingQuery so ResearchInput auto-submits.
  const searchParams = useSearchParams();
  const [pendingQuery, setPendingQuery] = useState(
    () => searchParams.get("q") ?? "",
  );
  const { isAuthenticated } = useAuth();

  const {
    sessionId,
    isConnected,
    agentStatuses,
    reportTokens,
    executiveSummary,
    isComplete,
    error: sseError,
    startSession,
    clearSession,
  } = useSSEContext();

  // Sources + confidence + summary arrive via API after workflow_completed.
  const [sources, setSources] = useState<Source[]>([]);
  const [confidenceScore, setConfidenceScore] = useState<number | null>(null);
  // Exec summary fetched from API (fallback when SSE connection was unstable).
  const [fetchedSummary, setFetchedSummary] = useState<string | null>(null);
  // Retry flag: DeepEval runs ~2–5s after workflow_completed, so score may be null on first fetch.
  const [retryConfidence, setRetryConfidence] = useState(false);

  // Cache-hit path: backend returned full report immediately (no SSE needed).
  const [cachedReport, setCachedReport] = useState<Omit<
    ResearchReportType,
    "session_id" | "created_at"
  > | null>(null);

  // The exact question the user submitted — shown as the report title. The input
  // box clears on submit, so without this the question would vanish from view
  // until the report is later reopened from history.
  const [submittedQuery, setSubmittedQuery] = useState("");

  // Cold start guard — Render free tier sleeps after 15 min inactivity.
  const [showWarmingUp, setShowWarmingUp] = useState(false);
  const warmingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Arm cold-start timer when a session is pending connection.
  useEffect(() => {
    if (sessionId && !isConnected && !isComplete) {
      warmingTimerRef.current = setTimeout(
        () => setShowWarmingUp(true),
        COLD_START_MS,
      );
    }
    if (isConnected || isComplete) {
      if (warmingTimerRef.current) clearTimeout(warmingTimerRef.current);
      setShowWarmingUp(false);
    }
    return () => {
      if (warmingTimerRef.current) clearTimeout(warmingTimerRef.current);
    };
  }, [sessionId, isConnected, isComplete]);

  // After workflow completes, fetch the full session to get sources + confidence + summary.
  useEffect(() => {
    if (!isComplete || !sessionId) return;
    getSessionDetail(sessionId)
      .then((data) => {
        if (data.report) {
          setSources(data.report.sources ?? []);
          setConfidenceScore(data.report.confidence_score ?? null);
          // SSE connection may have been unstable — always pull summary from API as fallback.
          if (data.report.executive_summary)
            setFetchedSummary(data.report.executive_summary);
          // DeepEval runs ~2–5s after workflow_completed → score may still be null. Schedule retry.
          if (!data.report.confidence_score) setRetryConfidence(true);
        }
      })
      .catch(() => null);
  }, [isComplete, sessionId]);

  // One-shot retry for confidence score (covers DeepEval timing gap).
  useEffect(() => {
    if (!retryConfidence || !sessionId) return;
    const timer = setTimeout(() => {
      getSessionDetail(sessionId)
        .then((data) => {
          if (data.report?.confidence_score) {
            setConfidenceScore(data.report.confidence_score);
          }
          setRetryConfidence(false);
        })
        .catch(() => setRetryConfidence(false));
    }, 5000);
    return () => clearTimeout(timer);
  }, [retryConfidence, sessionId]);

  // Cancel in-progress session when user navigates away or closes the tab.
  // sendBeacon fires reliably even during page teardown (unlike fetch).
  useEffect(() => {
    return () => {
      if (sessionId && !isComplete) {
        const base =
          process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
        navigator.sendBeacon(`${base}/research/cancel/${sessionId}/`);
      }
    };
  }, [sessionId, isComplete]);

  // ── Handlers ───────────────────────────────────────────────────────────────

  function handleSessionStarted(id: string, query: string) {
    setSources([]);
    setConfidenceScore(null);
    setCachedReport(null);
    setFetchedSummary(null);
    setRetryConfidence(false);
    setSubmittedQuery(query);
    setPendingQuery("");
    startSession(id);
  }

  function handleCachedResult(
    report: Omit<ResearchReportType, "session_id" | "created_at">,
    query: string,
  ) {
    clearSession();
    setSubmittedQuery(query);
    setCachedReport(report);
    setSources(report.sources ?? []);
    // Defense-in-depth: a cache hit may arrive before DeepEval has back-filled
    // the score (or if Redis is stale) → coerce undefined/missing to null so
    // ConfidenceBadge renders its pending skeleton instead of NaN%.
    setConfidenceScore(report.confidence_score ?? null);
    setFetchedSummary(null);
    setRetryConfidence(false);
  }

  // ── Derived display values ─────────────────────────────────────────────────

  // Prefer API-fetched summary over SSE (SSE may have gaps if connection was unstable).
  const displaySummary = cachedReport
    ? cachedReport.executive_summary
    : fetchedSummary ?? executiveSummary;
  const displayTokens = cachedReport ? cachedReport.full_report : reportTokens;
  const isActiveSession = !!sessionId || !!cachedReport;
  const isStreaming = !!sessionId && !isComplete;
  const reportComplete = isComplete || !!cachedReport;

  // A cache hit means the pipeline already ran to completion (no SSE this time)
  // → present every node as green. Otherwise, when the live workflow is complete,
  // any node still "running" missed its completion event — mark it done too.
  const displayAgentStatuses = cachedReport
    ? (Object.fromEntries(
        AGENT_NAMES.map((n) => [n, "completed"]),
      ) as typeof agentStatuses)
    : isComplete
      ? (Object.fromEntries(
          Object.entries(agentStatuses).map(([k, v]) => [
            k,
            v === "running" ? "completed" : v,
          ]),
        ) as typeof agentStatuses)
      : agentStatuses;

  // ── Shared header block (rendered in both layouts) ─────────────────────────

  const pageHeader = (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-blue-600 shadow-sm">
          <FlaskConical className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-gray-900">
            AI Research Assistant
          </h1>
          <p className="text-xs text-gray-500">
            Deep research for UPSC preparation · powered by an 8-agent AI
            pipeline
          </p>
        </div>
      </div>
      {isAuthenticated && (
        <Link
          href="/research_agent/history"
          className="flex-shrink-0 flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 hover:border-gray-300 hover:bg-gray-50 hover:text-gray-800 transition-colors shadow-sm"
        >
          <History className="h-3.5 w-3.5" />
          History
        </Link>
      )}
    </div>
  );

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <main className="px-4 py-8 sm:px-6 lg:px-8">
      {isActiveSession ? (
        /*
         * ACTIVE SESSION — full two-column grid from the very top.
         * LEFT  25%: Agent Pipeline, sticky — fills the top-left space.
         * RIGHT 75%: header + input + status pill + report, stacked vertically.
         *
         * Two-div pattern on the left (required for sticky-in-grid):
         *   Outer div = grid cell, stretches to full row height (= right column height).
         *   Inner div = sticky, content height only. Has thousands of px of scroll room
         *               inside the tall outer cell — sticky activates throughout the report.
         */
        <div className="grid grid-cols-1 gap-x-8 gap-y-6 lg:grid-cols-[1fr_3fr]">
          {/* LEFT — Agent Pipeline */}
          <div>
            <div className="flex flex-col gap-2 lg:sticky lg:top-4">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">
                Agent Pipeline
              </h2>
              <div className="relative">
                <ResearchGraphDynamic agentStatuses={displayAgentStatuses} />
                {showWarmingUp && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 rounded-xl bg-white/85 backdrop-blur-sm">
                    <ServerCrash className="h-8 w-8 text-gray-400" />
                    <p className="text-sm font-semibold text-gray-700">
                      Server warming up…
                    </p>
                    <p className="max-w-[220px] text-center text-xs text-gray-400">
                      Render free tier sleeps after 15 min · typically ready in
                      5–10 s
                    </p>
                    <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* RIGHT — header + input + status + report */}
          <div className="flex flex-col gap-5">
            {/* Header — aligns with top of Agent Pipeline */}
            {pageHeader}

            {/* Query input */}
            <ResearchInput
              onSessionStarted={handleSessionStarted}
              onCachedResult={handleCachedResult}
              disabled={isStreaming}
              pendingQuery={pendingQuery}
            />

            {/* Connection status pill */}
            {sessionId && (
              <div className="flex items-center gap-2 -mt-2">
                {isConnected ? (
                  <>
                    <span className="relative flex h-2.5 w-2.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
                      <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-green-500" />
                    </span>
                    <span className="text-xs font-medium text-green-700">
                      Connected · research in progress
                    </span>
                  </>
                ) : isComplete ? (
                  <>
                    <span className="h-2.5 w-2.5 rounded-full bg-blue-500" />
                    <span className="text-xs font-medium text-blue-700">
                      Research complete
                    </span>
                  </>
                ) : (
                  <>
                    <Loader2 className="h-3 w-3 animate-spin text-gray-400" />
                    <span className="text-xs text-gray-500">
                      Connecting to server…
                    </span>
                  </>
                )}
              </div>
            )}

            {/* SSE error */}
            {sseError && (
              <div className="flex items-start gap-3 rounded-xl border border-red-100 bg-red-50 px-5 py-4">
                <WifiOff className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-400" />
                <div>
                  <p className="text-sm font-medium text-red-700">{sseError}</p>
                  <p className="mt-0.5 text-xs text-red-400">
                    Refresh the page to start a new research session.
                  </p>
                </div>
              </div>
            )}

            {/* Research Report */}
            <div className="flex flex-col gap-2">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">
                Research Report
              </h2>
              <div className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
                {submittedQuery && (
                  <h3 className="mb-4 border-b border-gray-100 pb-3 text-lg font-bold leading-snug text-gray-900">
                    {submittedQuery}
                  </h3>
                )}
                <ResearchReport
                  sessionId={sessionId}
                  executiveSummary={displaySummary}
                  reportTokens={displayTokens}
                  sources={sources}
                  confidenceScore={confidenceScore}
                  isStreaming={isStreaming}
                  isComplete={reportComplete}
                />
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* NO ACTIVE SESSION — narrow centered layout */
        <div className="mx-auto max-w-3xl">
          <div className="mb-6">{pageHeader}</div>

          <div className="mb-6">
            <ResearchInput
              onSessionStarted={handleSessionStarted}
              onCachedResult={handleCachedResult}
              disabled={isStreaming}
              pendingQuery={pendingQuery}
            />
          </div>

          {sseError && (
            <div className="mt-6 flex items-start gap-3 rounded-xl border border-red-100 bg-red-50 px-5 py-4">
              <WifiOff className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-400" />
              <div>
                <p className="text-sm font-medium text-red-700">{sseError}</p>
                <p className="mt-0.5 text-xs text-red-400">
                  Refresh the page to start a new research session.
                </p>
              </div>
            </div>
          )}

          {!sseError && (
            <div className="flex flex-col items-center justify-center gap-5 rounded-2xl border border-dashed border-gray-200 py-10 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50">
                <FlaskConical className="h-8 w-8 text-blue-400" />
              </div>
              <div className="space-y-1.5">
                <p className="text-base font-semibold text-gray-800">
                  Start your research
                </p>
                <p className="mx-auto max-w-sm text-sm text-gray-400">
                  Type or speak a question above. The AI pipeline will research,
                  verify, and stream a structured report — live.
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-2 text-xs text-gray-400">
                {EXAMPLES.map((eg) => (
                  <button
                    key={eg}
                    type="button"
                    onClick={() => setPendingQuery(eg)}
                    className="rounded-full border border-gray-200 bg-gray-50 px-3 py-1 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600 transition-colors cursor-pointer"
                  >
                    {eg}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
