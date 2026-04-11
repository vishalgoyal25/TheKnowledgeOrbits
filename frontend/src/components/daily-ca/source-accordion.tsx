"use client";

import { useState } from "react";

/**
 * SourceAccordion — collapsible sources list below each article.
 * Shows the URLs from sources_used as clickable external links.
 */

interface Props {
  sources: string[];
}

function getDomain(url: unknown): string {
  const s = typeof url === "string" ? url : String(url ?? "");
  try {
    return new URL(s).hostname.replace(/^www\./, "");
  } catch {
    return s.slice(0, 40);
  }
}

function truncateUrl(url: unknown): string {
  const s = typeof url === "string" ? url : String(url ?? "");
  try {
    const u = new URL(s);
    const path = u.pathname.replace(/\/$/, "");
    const short = path.length > 50 ? path.slice(0, 50) + "…" : path;
    return u.hostname.replace(/^www\./, "") + short;
  } catch {
    return s.length > 70 ? s.slice(0, 70) + "…" : s;
  }
}

export function SourceAccordion({ sources }: Props) {
  const [open, setOpen] = useState(false);

  const validSources = sources.filter((s) => s && typeof s === "string");
  if (validSources.length === 0) return null;

  return (
    <div className="mt-4 rounded-lg border border-gray-200 overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-xs font-semibold text-gray-500 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span>📎</span>
          <span>
            Sources ({validSources.length}){" "}
            {!open && (
              <span className="font-normal">
                — {validSources.slice(0, 2).map(getDomain).join(", ")}
                {validSources.length > 2 && ` +${validSources.length - 2} more`}
              </span>
            )}
          </span>
        </div>
        <span className="text-gray-400">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="border-t border-gray-100 divide-y divide-gray-50">
          {validSources.map((url, i) => (
            <a
              key={i}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 text-xs text-blue-600 hover:bg-blue-50 transition-colors"
            >
              <span className="flex-shrink-0 text-gray-400">{i + 1}.</span>
              <span className="truncate">{truncateUrl(url)}</span>
              <span className="flex-shrink-0 text-gray-300 text-[10px]">
                ↗
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
