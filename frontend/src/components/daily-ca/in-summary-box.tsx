"use client";

import { useState } from "react";

/**
 * InSummaryBox — collapsible "In Summary" card.
 *
 * Primary source: `newsContext` — the article's news_context field, which is a
 * concise editorial summary of why the topic is in the news. Sentence-split into
 * bullet points (up to 3) so the box never duplicates body content.
 *
 * Fallback: `bodyMd` — used only when newsContext is absent or too short.
 * Extracts up to 3 meaningful sentences/bullets from the article body.
 */

interface Props {
  newsContext?: string;
  bodyMd?: string;
}

// ── Extraction helpers ─────────────────────────────────────────────────────────

/**
 * Split newsContext into up to 3 clean bullet points.
 * Handles both sentence-break (". ") and semicolon ("; ") delimiters.
 */
function extractFromNewsContext(text: string): string[] {
  if (!text || text.trim().length < 20) return [];

  // Try semicolon split first (structured news context)
  const bySemicolon = text
    .split(/;\s*/)
    .map((s) => s.trim().replace(/\.$/, ""))
    .filter((s) => s.length >= 20);

  if (bySemicolon.length >= 2) return bySemicolon.slice(0, 3);

  // Fall back to sentence split
  const bySentence = text
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length >= 20 && s.length <= 250);

  if (bySentence.length >= 1) return bySentence.slice(0, 3);

  // Single block — return as one point
  return [text.trim().slice(0, 250)];
}

/**
 * Fallback: extract 3 key points from article body markdown.
 * Used only when newsContext is absent/too short.
 */
function extractFromBodyMd(md: string): string[] {
  if (!md) return [];

  // Strategy 1: find bullet/numbered list items (min 30 chars, max 150)
  const bulletMatches = md.match(/^[-*•]\s+(.{30,150})$/gm) ?? [];
  const bullets = bulletMatches
    .map((l) =>
      l
        .replace(/^[-*•]\s+/, "")
        .replace(/\*\*/g, "")
        .trim(),
    )
    .filter((l) => !l.startsWith("#") && l.length > 20)
    .slice(0, 3);

  if (bullets.length >= 2) return bullets;

  // Strategy 2: first 3 meaningful sentences from cleaned text
  const cleaned = md
    .replace(/^#+\s.+$/gm, "") // remove headings
    .replace(/:::callout[\s\S]*?:::/g, "") // remove callouts
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1") // link text only
    .replace(/\*\*/g, "")
    .replace(/\*/g, "")
    .replace(/^\s*[-*•]\s+/gm, "")
    .replace(/\n+/g, " ")
    .trim();

  const sentences = cleaned
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 40 && s.length < 200);

  return sentences.slice(0, 3);
}

function getSummaryPoints(newsContext?: string, bodyMd?: string): string[] {
  // Primary: use news_context
  const fromContext = extractFromNewsContext(newsContext ?? "");
  if (fromContext.length >= 1) return fromContext;

  // Fallback: extract from body
  const fromBody = extractFromBodyMd(bodyMd ?? "");
  if (fromBody.length >= 1) return fromBody;

  return ["Key developments covered in this article."];
}

// ── Component ──────────────────────────────────────────────────────────────────

export function InSummaryBox({ newsContext, bodyMd }: Props) {
  const [open, setOpen] = useState(true);
  const points = getSummaryPoints(newsContext, bodyMd);

  return (
    <div className="my-4 rounded-xl border border-blue-200 bg-blue-50 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-semibold text-blue-800 hover:bg-blue-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-base">ℹ️</span>
          <span>In Summary</span>
        </div>
        <span className="text-blue-500 text-xs">{open ? "▲" : "▼"}</span>
      </button>

      {/* Content */}
      {open && (
        <ul className="px-4 pb-3 space-y-1.5">
          {points.map((point, i) => (
            <li key={i} className="flex gap-2 text-sm text-blue-900">
              <span className="flex-shrink-0 text-blue-400 font-bold mt-0.5">
                •
              </span>
              <span className="leading-relaxed">{point}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
