"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, FlaskConical, Loader2 } from "lucide-react";
import ResearchReport from "@/components/research_agent/ResearchReport";
import { getSessionDetail } from "@/lib/api/research-agent";
import type {
  ResearchReport as ResearchReportType,
  ResearchSession,
} from "@/types/research_agent";

type SessionWithReport = ResearchSession & {
  report: ResearchReportType | null;
};

export default function ResearchSessionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId =
    typeof params.sessionId === "string" ? params.sessionId : "";

  const [data, setData] = useState<SessionWithReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    setIsLoading(true);
    getSessionDetail(sessionId)
      .then(setData)
      .catch((err) => {
        const msg: string =
          err instanceof Error ? err.message : "Failed to load session.";
        // 404 or 403 → go back to history list
        if (
          msg.includes("404") ||
          msg.includes("403") ||
          msg.includes("not found")
        ) {
          router.replace("/research_agent/history");
        } else {
          setError(msg);
        }
      })
      .finally(() => setIsLoading(false));
  }, [sessionId, router]);

  // ── Loading ──────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 animate-pulse">
          <div className="h-5 w-32 rounded bg-gray-200" />
          <div className="h-7 w-64 rounded bg-gray-200" />
          <div className="mt-4 space-y-3">
            {[90, 100, 75, 85, 60, 95].map((w, i) => (
              <div
                key={i}
                className="h-3 rounded bg-gray-100"
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
        </div>
      </main>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────────

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center gap-4 rounded-xl border border-red-100 bg-red-50 py-16 text-center">
          <p className="text-sm font-medium text-red-700">{error}</p>
          <Link
            href="/research_agent/history"
            className="text-xs text-blue-600 underline hover:text-blue-800"
          >
            ← Back to history
          </Link>
        </div>
      </main>
    );
  }

  // ── Render ───────────────────────────────────────────────────────────────

  const report = data?.report ?? null;
  const hasReport = !!report;

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Back + header */}
      <div className="mb-6">
        <Link
          href="/research_agent/history"
          className="mb-4 inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Research History
        </Link>

        <div className="flex items-start gap-3 mt-3">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-blue-600 shadow-sm">
            <FlaskConical className="h-5 w-5 text-white" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-gray-900 leading-snug break-words">
              {data?.query ?? "Research Session"}
            </h1>
            <p className="mt-0.5 text-xs text-gray-400">
              {data?.created_at
                ? new Date(data.created_at).toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  })
                : ""}
              {data?.status === "completed"
                ? " · Completed"
                : ` · ${data?.status}`}
            </p>
          </div>
        </div>
      </div>

      {/* Report — static mode (no streaming, full text immediately) */}
      {hasReport ? (
        <div className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
          <ResearchReport
            sessionId={sessionId}
            executiveSummary={report.executive_summary}
            reportTokens={report.full_report}
            sources={report.sources ?? []}
            confidenceScore={report.confidence_score}
            isStreaming={false}
            isComplete={true}
          />
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-gray-200 py-16 text-center">
          {data?.status === "running" || data?.status === "pending" ? (
            <>
              <Loader2 className="h-6 w-6 animate-spin text-blue-400" />
              <p className="text-sm text-gray-500">
                Research still in progress…
              </p>
              <Link
                href="/research_agent"
                className="text-xs text-blue-600 underline"
              >
                Watch it live →
              </Link>
            </>
          ) : (
            <p className="text-sm text-gray-500">
              No report available for this session.
            </p>
          )}
        </div>
      )}
    </main>
  );
}
