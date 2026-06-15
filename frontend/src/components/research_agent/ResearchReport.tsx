"use client";

import { useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, Share2, ExternalLink } from "lucide-react";
import ConfidenceBadge from "./ConfidenceBadge";
import ExportButton from "./ExportButton";
import type { Source } from "@/types/research_agent";

// ── Props ─────────────────────────────────────────────────────────────────────
// Accepts plain props (not context) so it works in two modes:
//   1. Streaming (page.tsx reads SSEContext, passes growing strings)
//   2. Static   (history/[sessionId]/page.tsx passes complete report from API)

export interface ResearchReportProps {
  sessionId: string | null;
  executiveSummary: string;
  reportTokens: string; // growing during streaming; full text in static mode
  sources: Source[];
  confidenceScore: number | null;
  isStreaming: boolean; // true = tokens still arriving
  isComplete: boolean; // true = workflow_completed received / static load done
}

// ── Citation link injection ───────────────────────────────────────────────────
// Replaces [N] markers in LLM output with actual markdown links to source[N-1].
// Uses angle-bracket URL syntax (<url>) to safely handle URLs with parentheses.
function injectCitationLinks(text: string, sources: Source[]): string {
  if (!sources.length) return text;
  return text.replace(/\[(\d+)\]/g, (match, num) => {
    const idx = parseInt(num, 10) - 1;
    const source = sources[idx];
    return source ? `[${num}](<${source.url}>)` : match;
  });
}

// ── Markdown component overrides ──────────────────────────────────────────────
// Force external links to open in a new tab with safe rel attributes.
// No rehype-raw → no raw HTML passthrough → no XSS risk from LLM-generated content.
const MD_COMPONENTS = {
  a: ({
    href,
    children,
    ...rest
  }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-600 underline hover:text-blue-800 break-words"
      {...rest}
    >
      {children}
    </a>
  ),
};

// ── Sub-components ────────────────────────────────────────────────────────────

function StreamingCursor() {
  return (
    <span className="inline-block w-0.5 h-4 bg-blue-500 align-middle ml-0.5 animate-pulse" />
  );
}

function CredibilityPip({ score }: { score: number | null }) {
  if (score === null) return null;
  const pct = Math.round(score * 100);
  const color =
    score >= 0.8
      ? "bg-green-500"
      : score >= 0.6
        ? "bg-orange-400"
        : "bg-red-400";
  return (
    <span
      title={`Credibility: ${pct}%`}
      className={`inline-flex items-center gap-1 text-[10px] text-white px-1.5 py-0.5 rounded-full font-medium ${color}`}
    >
      {pct}%
    </span>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ResearchReport({
  sessionId,
  executiveSummary,
  reportTokens,
  sources,
  confidenceScore,
  isStreaming,
  isComplete,
}: ResearchReportProps) {
  const hasExecutive = executiveSummary.trim().length > 0;
  const hasReport = reportTokens.trim().length > 0;
  const hasContent = hasExecutive || hasReport;

  const handleCopy = useCallback(() => {
    const text = [
      executiveSummary ? `## Executive Summary\n\n${executiveSummary}` : "",
      reportTokens ? `## Full Report\n\n${reportTokens}` : "",
    ]
      .filter(Boolean)
      .join("\n\n---\n\n");
    navigator.clipboard.writeText(text).catch(() => null);
  }, [executiveSummary, reportTokens]);

  const handleShare = useCallback(() => {
    navigator.clipboard.writeText(window.location.href).catch(() => null);
  }, []);

  // ── Empty / pre-content state ──────────────────────────────────────────────
  if (!hasContent && !isStreaming) {
    return (
      <div className="flex flex-col items-center justify-center h-48 rounded-xl border border-dashed border-gray-200 text-gray-400 text-sm gap-2">
        <span>Report will appear here as the agents work…</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Confidence badge + action buttons */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <ConfidenceBadge score={isComplete ? confidenceScore : null} />
        {isComplete && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCopy}
              title="Copy report to clipboard"
              className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
            >
              <Copy className="w-3.5 h-3.5" />
              Copy
            </button>
            <button
              type="button"
              onClick={handleShare}
              title="Copy page link to clipboard"
              className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
            >
              <Share2 className="w-3.5 h-3.5" />
              Share
            </button>
          </div>
        )}
      </div>

      {/* Executive Summary */}
      {hasExecutive && (
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
            Executive Summary
          </h3>
          <div
            className="rounded-xl bg-blue-50 border border-blue-100 px-5 py-4 text-sm text-gray-700 leading-relaxed
            [&_p]:mb-3 [&_p]:leading-relaxed
            [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-3
            [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-3
            [&_li]:mb-1 [&_strong]:font-semibold"
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={MD_COMPONENTS}
            >
              {injectCitationLinks(executiveSummary, sources)}
            </ReactMarkdown>
            {isStreaming && !hasReport && <StreamingCursor />}
          </div>
        </section>
      )}

      {/* Full Report */}
      {hasReport && (
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
            Full Report
          </h3>
          <div
            className="text-sm text-gray-800 leading-relaxed
            [&_p]:mb-4 [&_p]:leading-relaxed
            [&_h1]:text-lg [&_h1]:font-bold [&_h1]:mt-6 [&_h1]:mb-3
            [&_h2]:text-base [&_h2]:font-bold [&_h2]:mt-6 [&_h2]:mb-2
            [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mt-4 [&_h3]:mb-2
            [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-4
            [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-4
            [&_li]:mb-1.5 [&_strong]:font-semibold
            [&_blockquote]:border-l-4 [&_blockquote]:border-blue-200 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-gray-600 [&_blockquote]:my-4"
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={MD_COMPONENTS}
            >
              {injectCitationLinks(reportTokens, sources)}
            </ReactMarkdown>
            {isStreaming && <StreamingCursor />}
          </div>
        </section>
      )}

      {/* Loading skeleton while streaming hasn't started yet */}
      {isStreaming && !hasContent && (
        <div className="space-y-3">
          {[80, 100, 60, 90].map((w, i) => (
            <div
              key={i}
              className="h-3 rounded bg-gray-100 animate-pulse"
              style={{ width: `${w}%` }}
            />
          ))}
        </div>
      )}

      {/* Sources */}
      {sources.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
            Sources
          </h3>
          <ol className="flex flex-col gap-2">
            {sources.map((src, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <span className="text-gray-400 tabular-nums min-w-[1.5rem] text-right">
                  {i + 1}.
                </span>
                <div className="flex flex-col gap-0.5 min-w-0">
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 underline break-words leading-snug flex items-center gap-1"
                  >
                    {src.title || src.url}
                    <ExternalLink className="w-3 h-3 flex-shrink-0 opacity-60" />
                  </a>
                  <span className="text-[11px] text-gray-400 break-all">
                    {src.url}
                  </span>
                </div>
                <CredibilityPip score={src.credibility_score} />
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* Export — only after workflow is fully complete */}
      {isComplete && sessionId && (
        <div className="pt-2 border-t border-gray-100">
          <ExportButton sessionId={sessionId} />
        </div>
      )}
    </div>
  );
}
