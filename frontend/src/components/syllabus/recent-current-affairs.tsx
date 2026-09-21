"use client";

import Image from "next/image";
import Link from "next/link";
import { Newspaper } from "lucide-react";
import { useEffect, useState } from "react";

import {
  getArticlesByNode,
  type DailyCaArticleList,
  type SyllabusScope,
} from "@/lib/api/daily-ca";
import { cn } from "@/lib/utils";

/**
 * RecentCurrentAffairs (G3.14c) — the daily-CA articles filed under one
 * syllabus node (topic / module / subject), newest first, on the hierarchy
 * pages. The reverse direction of the Explore Syllabus card.
 *
 * CLIENT-SIDE ONLY, on purpose. The hierarchy pages are ISR-cached for a
 * week (topics) or a day (modules, subjects) and `C2` forbids lowering that,
 * so fresh news cannot live in their HTML. This block fetches from the
 * browser straight to Render — the `/daily-ca` feed's own pattern (§4.1):
 * zero ISR writes, zero Vercel edge cost, always today's list.
 *
 * Renders NOTHING when the node has no articles (or the API fails) — never
 * an empty frame, never a red box on a public page. Thumbnails go through
 * the global Cloudinary loader (`next.config.ts`), so `next/image` costs no
 * Vercel transformation; `sizes="80px"` asks Cloudinary for a tiny file.
 *
 * Frame: the hierarchy pages' tokens (`border-border`, `bg-card`); rows: the
 * daily-CA right panel's shape (badge map, date, two-line title).
 */

const PAGE_SIZE = 10;

const GS_COLORS: Record<string, string> = {
  GS1: "bg-purple-100 text-purple-700",
  GS2: "bg-blue-100 text-blue-700",
  GS3: "bg-green-100 text-green-700",
  GS4: "bg-orange-100 text-orange-700",
  CSAT: "bg-gray-100 text-gray-600",
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

type Status = "loading" | "ready" | "empty" | "error";

export interface RecentCurrentAffairsProps {
  scope: SyllabusScope;
  /** The node's UUID — the API filters on the FK, never on the slug. */
  nodeId: string;
  title?: string;
  className?: string;
}

export default function RecentCurrentAffairs({
  scope,
  nodeId,
  title = "In the news",
  className,
}: RecentCurrentAffairsProps) {
  const [items, setItems] = useState<DailyCaArticleList[]>([]);
  const [count, setCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [status, setStatus] = useState<Status>("loading");
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setItems([]);
    getArticlesByNode(scope, nodeId, { limit: PAGE_SIZE, offset: 0 })
      .then((res) => {
        if (cancelled) return;
        // An article without a slug has no URL (the /daily-ca/article/null
        // lesson, G1.5) — drop it before it can be linked.
        const rows = res.articles.filter((a) => Boolean(a.slug));
        if (rows.length === 0) {
          setStatus("empty");
          return;
        }
        setItems(rows);
        setCount(res.count);
        setHasMore(res.has_more);
        setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [scope, nodeId]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const res = await getArticlesByNode(scope, nodeId, {
        limit: PAGE_SIZE,
        offset: items.length,
      });
      setItems((prev) => [...prev, ...res.articles.filter((a) => a.slug)]);
      setHasMore(res.has_more);
    } catch {
      setHasMore(false);
    } finally {
      setLoadingMore(false);
    }
  };

  if (status === "empty" || status === "error") return null;

  return (
    <section
      aria-label={title}
      className={cn(
        "rounded-xl border border-border bg-card overflow-hidden",
        className,
      )}
    >
      <div className="px-4 py-2.5 border-b border-border/60 flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          <Newspaper className="h-3.5 w-3.5" aria-hidden="true" />
          {title}
        </p>
        {status === "ready" && (
          <span className="text-xs text-muted-foreground">{count}</span>
        )}
      </div>

      {status === "loading" ? (
        <ul className="divide-y divide-border/60" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <li key={i} className="flex gap-3 px-4 py-3">
              <div className="h-14 w-20 shrink-0 rounded-md bg-muted animate-pulse" />
              <div className="flex-1 space-y-2 py-1">
                <div className="h-3 w-24 rounded bg-muted animate-pulse" />
                <div className="h-3 w-full rounded bg-muted animate-pulse" />
                <div className="h-3 w-3/4 rounded bg-muted animate-pulse" />
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <ul className="divide-y divide-border/60">
          {items.map((a) => {
            const gsColor = GS_COLORS[a.gs_paper] ?? GS_COLORS["CSAT"];
            return (
              <li key={a.id}>
                <Link
                  href={`/daily-ca/article/${a.slug}`}
                  className="flex gap-3 px-4 py-3 hover:bg-muted/40 transition-colors"
                >
                  {a.hero_image_url ? (
                    <div className="relative h-14 w-20 shrink-0 overflow-hidden rounded-md bg-muted">
                      <Image
                        src={a.hero_image_url}
                        alt=""
                        fill
                        sizes="80px"
                        className="object-cover"
                      />
                    </div>
                  ) : (
                    <div className="flex h-14 w-20 shrink-0 items-center justify-center rounded-md bg-muted">
                      <Newspaper
                        className="h-4 w-4 text-muted-foreground/50"
                        aria-hidden="true"
                      />
                    </div>
                  )}
                  <div className="min-w-0">
                    <div className="mb-1 flex items-center gap-1.5">
                      {a.gs_paper && (
                        <span
                          className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold ${gsColor}`}
                        >
                          {a.gs_paper}
                        </span>
                      )}
                      <span className="text-[10px] text-muted-foreground">
                        {formatDate(a.published_date)}
                      </span>
                    </div>
                    <p className="text-xs font-medium text-foreground leading-snug line-clamp-2">
                      {a.title}
                    </p>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}

      {status === "ready" && hasMore && (
        <div className="px-4 py-3 border-t border-border/60">
          <button
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
            className="w-full rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary disabled:opacity-60"
          >
            {loadingMore ? "Loading…" : "Load more"}
          </button>
        </div>
      )}
    </section>
  );
}
