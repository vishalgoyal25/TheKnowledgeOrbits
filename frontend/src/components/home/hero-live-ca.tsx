"use client";

/**
 * Live Current Affairs preview for the homepage hero.
 *
 * Extracted verbatim from home-page-client.tsx during G2 — same props, same
 * behaviour, same markup structure. Only the visual language changed: one
 * radius via tokens, and the emerald->teal header gradient replaced with a
 * flat highlight band, since G2 sanctions a single gradient reserved for the
 * primary CTA.
 *
 * The GS paper badge colours are deliberately untouched. They are SEMANTIC —
 * readers learn that GS2 is blue and GS3 is green — so they are not part of
 * the accent-reduction sweep.
 */
import Link from "next/link";
import { ArrowRight, Newspaper } from "lucide-react";

import type { DailyCaArticleList } from "@/lib/api/daily-ca";

const GS_BADGE_COLORS: Record<string, string> = {
  GS1: "bg-purple-100 text-purple-700",
  GS2: "bg-blue-100 text-blue-700",
  GS3: "bg-green-100 text-green-700",
  GS4: "bg-orange-100 text-orange-700",
  CSAT: "bg-gray-100 text-gray-600",
};

// Pure presentation component. loading=false when articles are ISR-baked.
export function HeroLiveCA({
  articles,
  loading,
}: {
  articles: DailyCaArticleList[];
  loading: boolean;
}) {
  const today = new Date().toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border bg-muted/60 px-4 py-3">
        <div className="flex items-center gap-2">
          <Newspaper className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">
            Today&apos;s Current Affairs
          </span>
          <span className="hidden text-xs text-muted-foreground sm:inline">
            {today}
          </span>
        </div>
        <Link
          href="/daily-ca"
          className="flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-primary"
        >
          View All <ArrowRight className="h-3 w-3" />
        </Link>
      </div>

      <div className="divide-y divide-border">
        {loading ? (
          [1, 2, 3, 4].map((i) => (
            <div key={i} className="flex animate-pulse gap-3 px-4 py-3">
              <div className="mt-0.5 h-5 w-5 flex-shrink-0 rounded-full bg-muted" />
              <div className="flex-1 space-y-1.5">
                <div className="h-3 w-1/4 rounded bg-muted" />
                <div className="h-4 rounded bg-muted" />
                <div className="h-3 w-3/4 rounded bg-muted/60" />
              </div>
            </div>
          ))
        ) : articles.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-sm font-medium text-muted-foreground">
              No articles yet today.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Check back soon — we publish daily!
            </p>
          </div>
        ) : (
          articles.map((a, i) => {
            const gsColor =
              GS_BADGE_COLORS[a.gs_paper] ?? GS_BADGE_COLORS["CSAT"];
            return (
              <Link
                key={a.id}
                href={`/daily-ca/article/${a.slug}`}
                className="group flex items-start gap-3 px-4 py-3 transition-colors hover:bg-muted/50"
              >
                <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-semibold text-primary">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="mb-0.5 flex items-center gap-1.5">
                    <span
                      className={`rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${gsColor}`}
                    >
                      {a.gs_paper}
                    </span>
                    <span className="truncate text-[10px] text-muted-foreground">
                      {a.subject_name}
                    </span>
                  </div>
                  <p className="line-clamp-2 text-xs font-medium leading-snug text-foreground transition-colors group-hover:text-primary">
                    {a.title}
                  </p>
                </div>
                <ArrowRight className="mt-1 h-3 w-3 flex-shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
              </Link>
            );
          })
        )}
      </div>

      <div className="flex items-center justify-between border-t border-border bg-muted/40 px-4 py-2.5">
        <span className="text-[11px] text-muted-foreground">
          {articles.length > 0
            ? `Showing ${articles.length} of today's articles`
            : "Updated daily"}
        </span>
        <Link
          href="/daily-ca"
          className="flex items-center gap-1 text-xs font-medium text-primary transition-colors hover:text-primary/80"
        >
          Full feed <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}
