"use client";

import { useState } from "react";
import type { SourceItem } from "@/lib/api/daily-ca";

/**
 * SourceAccordion — collapsible source attribution section below each article.
 *
 * Shows the news sources whose content was used as context for generating
 * this article. Renders as a professional dropdown with source name + URL.
 *
 * Placed below the Tags section — provides authenticity and verification
 * for the reader. Clicking a source opens the original article in a new tab.
 */

interface Props {
  sources: SourceItem[];
}

function getDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url.slice(0, 40);
  }
}

function truncatePath(url: string): string {
  try {
    const u = new URL(url);
    const path = u.pathname.replace(/\/$/, "");
    const short = path.length > 45 ? path.slice(0, 45) + "…" : path;
    return u.hostname.replace(/^www\./, "") + short;
  } catch {
    return url.length > 70 ? url.slice(0, 70) + "…" : url;
  }
}

export function SourceAccordion({ sources }: Props) {
  const [open, setOpen] = useState(false);

  const validSources = sources.filter(
    (s) => s && typeof s === "object" && s.url && s.url.startsWith("http"),
  );

  if (validSources.length === 0) return null;

  const previewDomains = validSources
    .slice(0, 2)
    .map((s) => getDomain(s.url))
    .join(", ");

  return (
    <div className="mt-5 rounded-xl border border-gray-200 overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-base">📰</span>
          <div className="text-left">
            <p className="text-xs font-semibold text-gray-700">
              News Sources &amp; Attribution
            </p>
            {!open && (
              <p className="text-[11px] text-gray-400 mt-0.5">
                {previewDomains}
                {validSources.length > 2 && ` +${validSources.length - 2} more`}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-[10px] text-gray-400 hidden sm:inline">
            {validSources.length} source{validSources.length !== 1 ? "s" : ""}
          </span>
          <span className="text-gray-400 text-xs">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-100 bg-white">
          <p className="px-4 py-2 text-[11px] text-gray-400 border-b border-gray-50">
            This article was generated using the following news sources as
            context. All rights belong to the respective publishers.
          </p>
          <div className="divide-y divide-gray-50">
            {validSources.map((source, i) => (
              <a
                key={i}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start gap-3 px-4 py-3 hover:bg-blue-50 transition-colors group"
              >
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-gray-100 text-[10px] text-gray-500 flex items-center justify-center mt-0.5">
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className="text-[10px] font-semibold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                      {source.source_name || getDomain(source.url)}
                    </span>
                  </div>
                  {source.title && (
                    <p className="text-xs text-gray-700 leading-snug mb-0.5 line-clamp-2 group-hover:text-blue-700 transition-colors">
                      {source.title}
                    </p>
                  )}
                  <p className="text-[10px] text-gray-400 truncate">
                    {truncatePath(source.url)}
                  </p>
                </div>
                <span className="flex-shrink-0 text-gray-300 text-xs group-hover:text-blue-400 transition-colors mt-1">
                  ↗
                </span>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
