"use client";

import { useState } from "react";

/**
 * InSummaryBox — collapsible "In Summary" card.
 *
 * Primary source: `bodyMd` — extracts the opening lede paragraph from the
 * LLM-written article body, which is always a high-quality 2-3 sentence
 * summary of what happened, why it matters, and what's next.
 *
 * Fallback: `newsContext` — used only when bodyMd lede extraction fails.
 * Last resort: first bullet items found anywhere in the body.
 */

interface Props {
  newsContext?: string;
  bodyMd?: string;
}

// ── Extraction helpers ─────────────────────────────────────────────────────────

/**
 * PRIMARY: Extract the opening lede paragraph from the article body.
 *
 * The LLM always writes the first section's opening paragraph as a concise
 * news-style summary. We grab it, clean markdown, split into up to 3 sentences.
 *
 * Rules:
 *  - Skip headings (## / ###)
 *  - Skip callout blocks (:::callout … :::)
 *  - Skip blank lines
 *  - Take the FIRST paragraph of real prose text
 *  - Split into sentences and return up to 3
 */
function extractLedeParagraph(md: string): string[] {
  if (!md) return [];

  // Strip callout blocks entirely
  const stripped = md.replace(/:::callout[\s\S]*?:::/g, "");

  const lines = stripped.split("\n");
  const paraLines: string[] = [];
  let inPara = false;

  for (const raw of lines) {
    const line = raw.trim();

    // Skip headings
    if (line.startsWith("#")) continue;

    // Skip blank lines — if we were collecting a paragraph, stop
    if (line === "") {
      if (inPara && paraLines.length > 0) break; // end of first paragraph
      continue;
    }

    // Skip standalone bullet/numbered lines (we want prose, not bullet lists)
    if (/^[-*•]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      // If we haven't started collecting prose yet, keep looking
      if (!inPara) continue;
      // If mid-paragraph bullets appear, stop
      break;
    }

    // This is a prose line — clean markdown and collect
    const clean = line
      .replace(/\*\*/g, "")
      .replace(/\*/g, "")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/`/g, "")
      .trim();

    if (clean.length > 20) {
      paraLines.push(clean);
      inPara = true;
    }
  }

  if (paraLines.length === 0) return [];

  // Join all lines of the paragraph, then split into sentences
  const paragraph = paraLines.join(" ");
  const sentences = paragraph
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 30);

  return sentences.slice(0, 3);
}

/**
 * FALLBACK: Split newsContext into up to 3 clean bullet points.
 * Skips known garbage fallback strings written by the proposal generator.
 */
function extractFromNewsContext(text: string): string[] {
  if (!text || text.trim().length < 30) return [];

  // Reject known garbage fallback patterns
  if (
    /^Recent development on .+\. Review source articles\.?$/i.test(text.trim())
  ) {
    return [];
  }
  if (/review source articles/i.test(text)) return [];

  // Try semicolon split first (structured news context)
  const bySemicolon = text
    .split(/;\s*/)
    .map((s) => s.trim().replace(/\.$/, ""))
    .filter((s) => s.length >= 25);

  if (bySemicolon.length >= 2) return bySemicolon.slice(0, 3);

  // Fall back to sentence split
  const bySentence = text
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length >= 25 && s.length <= 280);

  if (bySentence.length >= 1) return bySentence.slice(0, 3);

  // Single block — return as one point
  return [text.trim().slice(0, 280)];
}

/**
 * LAST RESORT: pick first bullet items from anywhere in the article body.
 */
function extractBulletsFromBody(md: string): string[] {
  if (!md) return [];

  const bulletMatches = md.match(/^[-*•]\s+(.{30,150})$/gm) ?? [];
  return bulletMatches
    .map((l) =>
      l
        .replace(/^[-*•]\s+/, "")
        .replace(/\*\*/g, "")
        .trim(),
    )
    .filter((l) => l.length > 25)
    .slice(0, 3);
}

function getSummaryPoints(newsContext?: string, bodyMd?: string): string[] {
  // Primary: lede paragraph from LLM article body
  const fromLede = extractLedeParagraph(bodyMd ?? "");
  if (fromLede.length >= 1) return fromLede;

  // Secondary: news_context field (if it's meaningful, not a fallback placeholder)
  const fromContext = extractFromNewsContext(newsContext ?? "");
  if (fromContext.length >= 1) return fromContext;

  // Last resort: first bullets from body
  const fromBullets = extractBulletsFromBody(bodyMd ?? "");
  if (fromBullets.length >= 1) return fromBullets;

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
