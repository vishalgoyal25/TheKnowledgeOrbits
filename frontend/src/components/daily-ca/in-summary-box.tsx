"use client";

import { useState } from "react";

/**
 * InSummaryBox — collapsible "In Summary" card.
 * Extracts 3 key points from the article markdown body automatically.
 */

interface Props {
  bodyMd: string;
}

function extractSummaryPoints(md: string): string[] {
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

  return sentences.slice(0, 3).length > 0
    ? sentences.slice(0, 3)
    : ["This article covers key UPSC-relevant current affairs developments."];
}

export function InSummaryBox({ bodyMd }: Props) {
  const [open, setOpen] = useState(true);
  const points = extractSummaryPoints(bodyMd);

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
