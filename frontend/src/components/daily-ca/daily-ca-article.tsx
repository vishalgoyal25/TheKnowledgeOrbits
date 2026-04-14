"use client";

import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { DailyCaArticleDetail } from "@/lib/api/daily-ca";
import { InSummaryBox } from "./in-summary-box";
import { CalloutBlock } from "./callout-block";
import { TagChips } from "./tag-chips";
import { SourceAccordion } from "./source-accordion";

/**
 * DailyCaArticle — renders one full CA article in the feed.
 * Handles: callout pre-processing, markdown rendering, summary box,
 * tag chips, source accordion, and prev/next navigation hints.
 */

interface Props {
  article: DailyCaArticleDetail;
  index: number;
  total: number;
  isActive: boolean;
  onPrev: (() => void) | null;
  onNext: (() => void) | null;
}

// ── Callout pre-processor ─────────────────────────────────────────────────────

type Part =
  | { type: "text"; content: string }
  | { type: "callout"; content: string };

function splitCallouts(md: string): Part[] {
  const parts: Part[] = [];
  const regex = /:::callout\n([\s\S]*?)\n:::/g;
  let last = 0;
  let m: RegExpExecArray | null;
  // eslint-disable-next-line no-cond-assign
  while ((m = regex.exec(md)) !== null) {
    if (m.index > last)
      parts.push({ type: "text", content: md.slice(last, m.index) });
    parts.push({ type: "callout", content: m[1] });
    last = m.index + m[0].length;
  }
  if (last < md.length) parts.push({ type: "text", content: md.slice(last) });
  return parts;
}

// ── GS Paper badge ────────────────────────────────────────────────────────────

const GS_COLORS: Record<string, string> = {
  GS1: "bg-purple-100 text-purple-700 border-purple-200",
  GS2: "bg-blue-100 text-blue-700 border-blue-200",
  GS3: "bg-green-100 text-green-700 border-green-200",
  GS4: "bg-orange-100 text-orange-700 border-orange-200",
  CSAT: "bg-gray-100 text-gray-600 border-gray-200",
};

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function estimateReadTime(md: string): number {
  const words = md.split(/\s+/).length;
  return Math.max(1, Math.round(words / 200));
}

// ── Custom markdown components ────────────────────────────────────────────────
// F1 (FEATURES3): Full typographic upgrade — larger, more readable, better spaced.
// Paragraph structure: each <p> gets generous line-height + bottom margin so
// multi-paragraph sections feel distinct and breathable (not a wall of text).

const markdownComponents = {
  // ## Section headings — clearly larger than body, with a coloured underline accent
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="text-xl font-bold text-gray-900 mt-8 mb-3 pb-2 border-b-2 border-blue-100 tracking-tight leading-snug">
      {children}
    </h2>
  ),

  // ### Sub-headings — one step down, still prominent
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="text-lg font-semibold text-gray-800 mt-6 mb-2 leading-snug">
      {children}
    </h3>
  ),

  // Paragraphs — base text size, generous line-height for long reads,
  // clear bottom margin separates each paragraph visually
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="text-base leading-7 text-gray-700 mb-4">{children}</p>
  ),

  // Unordered lists — slightly more spacing between items for readability
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="my-4 space-y-2 pl-2">{children}</ul>
  ),

  // Ordered lists
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="my-4 space-y-2 pl-5 list-decimal">{children}</ol>
  ),

  // List items — base size, bullet dot replaced with a styled accent
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="text-base text-gray-700 leading-7 flex gap-2.5">
      <span className="flex-shrink-0 text-blue-400 font-bold mt-0.5">•</span>
      <span>{children}</span>
    </li>
  ),

  // Bold — slightly deeper colour for contrast against body text
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-gray-900">{children}</strong>
  ),

  // Inline code
  code: ({ children }: { children?: React.ReactNode }) => (
    <code className="text-sm bg-gray-100 text-gray-800 rounded px-1.5 py-0.5 font-mono">
      {children}
    </code>
  ),

  // Concept links and external links — base size, readable blue, underlined
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a
      href={href}
      className="text-base text-blue-600 underline underline-offset-2 hover:text-blue-800 transition-colors font-medium"
    >
      {children}
    </a>
  ),

  // Blockquote — used for callout-style notes and pull quotes
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="my-5 border-l-4 border-blue-300 bg-blue-50/50 pl-4 pr-3 py-3 rounded-r-xl text-base text-gray-600 italic leading-7">
      {children}
    </blockquote>
  ),

  // Horizontal rule — clean visual section break
  hr: () => <hr className="my-6 border-t border-gray-200" />,

  // Tables — rounded card with shadow, clearly readable at base size
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="overflow-x-auto my-6 rounded-xl shadow-sm border border-gray-200">
      <table className="min-w-full text-sm border-collapse">{children}</table>
    </div>
  ),

  // Table header cells — slightly larger than before, bolder weight
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="bg-gray-50 px-4 py-2.5 text-left text-sm font-semibold text-gray-700 border-b border-gray-200 whitespace-nowrap">
      {children}
    </th>
  ),

  // Table data cells — base small size but comfortable padding
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="px-4 py-2.5 text-sm text-gray-700 border-b border-gray-100 align-top">
      {children}
    </td>
  ),
};

// ── Main Component ────────────────────────────────────────────────────────────

export function DailyCaArticle({
  article,
  index,
  total,
  isActive,
  onPrev,
  onNext,
}: Props) {
  const gsColor = GS_COLORS[article.gs_paper] ?? GS_COLORS["CSAT"];
  const parts = splitCallouts(article.body_md_processed || "");
  const readMin = estimateReadTime(article.body_md_processed || "");

  return (
    <article
      id={`article-${article.id}`}
      className={`rounded-2xl border bg-white transition-all ${
        isActive ? "border-blue-200 shadow-md" : "border-gray-200 shadow-sm"
      }`}
    >
      {/* Article Header */}
      <div className="px-6 pt-5 pb-3">
        {/* Meta row */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {article.gs_paper && (
            <span
              className={`rounded-full border px-2.5 py-0.5 text-xs font-bold ${gsColor}`}
            >
              {article.gs_paper}
            </span>
          )}
          <span className="text-xs text-gray-500">{article.subject_name}</span>
          <span className="text-xs text-gray-300">·</span>
          <span className="text-xs text-gray-400">
            {formatDate(article.published_date)}
          </span>
          <span className="text-xs text-gray-300">·</span>
          <span className="text-xs text-gray-400">{readMin} min read</span>
          <span className="text-xs text-gray-300">·</span>
          <span className="text-xs text-gray-400">
            {index + 1}/{total}
          </span>
        </div>

        {/* Title */}
        <h1 className="text-xl font-bold leading-snug tracking-tight mb-2">
          <Link
            href={`/daily-ca/article/${article.slug}`}
            className="text-blue-900 hover:text-blue-700 transition-colors"
          >
            {article.title}
          </Link>
        </h1>

        {/* News context */}
        {article.news_context && (
          <p className="text-sm text-gray-500 italic leading-relaxed mb-3 border-l-2 border-blue-200 pl-3">
            {article.news_context}
          </p>
        )}

        {/* In Summary — primary: news_context; fallback: body markdown */}
        {(article.news_context || article.body_md_processed) && (
          <InSummaryBox
            newsContext={article.news_context ?? undefined}
            bodyMd={article.body_md_processed ?? undefined}
          />
        )}
      </div>

      {/* Article Body */}
      <div className="px-6 pb-6 antialiased">
        {parts.map((part, i) =>
          part.type === "callout" ? (
            <CalloutBlock key={i} content={part.content} />
          ) : (
            <ReactMarkdown
              key={i}
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {part.content}
            </ReactMarkdown>
          ),
        )}

        {/* Tags */}
        {article.tags.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <TagChips tags={article.tags} />
          </div>
        )}

        {/* Sources */}
        <SourceAccordion sources={article.sources_used ?? []} />

        {/* Prev / Next navigation */}
        {(onPrev || onNext) && (
          <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100">
            <button
              onClick={onPrev ?? undefined}
              disabled={!onPrev}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              ← Prev
            </button>
            <span className="text-xs text-gray-300">
              {index + 1} of {total}
            </span>
            <button
              onClick={onNext ?? undefined}
              disabled={!onNext}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </article>
  );
}
