"use client";

import { useCallback, useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { getArchive, DailyCaArticleList } from "@/lib/api/daily-ca";

// ── Category label map ────────────────────────────────────────────────────────
// Keep in sync with NEWS_CATEGORY_CHOICES in backend/engines/daily_ca/models.py

const CATEGORY_LABELS: Record<string, string> = {
  national: "National",
  international: "International",
  "geo-politics": "Geo-Politics",
  "geo-economics": "Geo-Economics",
  economy: "Economy & Business",
  "science-tech": "Science & Technology",
  environment: "Environment & Climate",
  society: "Society & Culture",
  "law-justice": "Law & Justice",
  defence: "Defence & Security",
  health: "Health",
  "sports-awards": "Sports & Awards",
};

// ── Article list row ──────────────────────────────────────────────────────────

function NewsArticleRow({ article }: { article: DailyCaArticleList }) {
  const categoryLabel =
    CATEGORY_LABELS[article.news_category] ?? article.news_category;

  const dateLabel = new Date(article.published_date).toLocaleDateString(
    "en-IN",
    { day: "numeric", month: "short", year: "numeric" },
  );

  return (
    <Link
      href={`/daily-ca/article/${article.slug}`}
      className="group flex items-start gap-4 px-5 py-4 bg-white hover:bg-blue-50/40 transition-colors border-b border-gray-100 last:border-b-0"
    >
      {/* Left: meta + title + context */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
          <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700 shrink-0">
            {categoryLabel}
          </span>
          {article.gs_paper && (
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500 shrink-0">
              {article.gs_paper}
            </span>
          )}
        </div>

        <h3 className="text-sm font-semibold text-gray-900 leading-snug mb-1 group-hover:text-blue-700 transition-colors line-clamp-2">
          {article.title}
        </h3>

        {article.news_context && (
          <p className="text-xs text-gray-400 line-clamp-1">
            {article.news_context}
          </p>
        )}
      </div>

      {/* Right: date + read arrow */}
      <div className="shrink-0 flex flex-col items-end gap-2 pt-0.5">
        <span className="text-[11px] text-gray-400 whitespace-nowrap">
          {dateLabel}
        </span>
        <span className="text-xs font-semibold text-blue-400 group-hover:text-blue-600 transition-colors">
          Read →
        </span>
      </div>
    </Link>
  );
}

// ── Inner page (uses useSearchParams — must be wrapped in Suspense) ────────────

function NewsPageInner() {
  const searchParams = useSearchParams();
  const activeCategory = searchParams.get("category") ?? "all";

  const [allArticles, setAllArticles] = useState<DailyCaArticleList[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [oldestDate, setOldestDate] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Derive oldest date from articles loaded so far (used as cursor for load more)
  const updateOldestDate = (articles: DailyCaArticleList[]) => {
    if (articles.length === 0) return;
    const dates = articles.map((a) => a.published_date);
    setOldestDate(dates.reduce((min, d) => (d < min ? d : min)));
  };

  const fetchArticles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // P2.6 — fetch 10 days at a time instead of all 300 articles at once
      const archive = await getArchive({ days: 10 });
      const flat = archive.archive.flatMap((day) => day.articles);
      flat.sort((a, b) => {
        const dateDiff =
          new Date(b.published_date).getTime() -
          new Date(a.published_date).getTime();
        if (dateDiff !== 0) return dateDiff;
        return a.order_on_date - b.order_on_date;
      });
      setAllArticles(flat);
      setHasMore(archive.has_more);
      updateOldestDate(flat);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load articles");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMore = useCallback(async () => {
    if (!oldestDate || loadingMore) return;
    setLoadingMore(true);
    try {
      const archive = await getArchive({ days: 10, before: oldestDate });
      const flat = archive.archive.flatMap((day) => day.articles);
      flat.sort((a, b) => {
        const dateDiff =
          new Date(b.published_date).getTime() -
          new Date(a.published_date).getTime();
        if (dateDiff !== 0) return dateDiff;
        return a.order_on_date - b.order_on_date;
      });
      setAllArticles((prev) => {
        const combined = [...prev, ...flat];
        updateOldestDate(combined);
        return combined;
      });
      setHasMore(archive.has_more);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load more articles");
    } finally {
      setLoadingMore(false);
    }
  }, [oldestDate, loadingMore]);

  useEffect(() => {
    fetchArticles();
  }, [fetchArticles]);

  const filtered =
    activeCategory === "all"
      ? allArticles
      : allArticles.filter((a) => a.news_category === activeCategory);

  const activeCategoryLabel =
    activeCategory === "all"
      ? "All News"
      : CATEGORY_LABELS[activeCategory] ?? activeCategory;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Page header */}
      <div className="bg-white border-b border-gray-200 px-4 py-4 max-w-[860px] mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-900 tracking-tight">
              {activeCategoryLabel}
            </h1>
            {!loading && (
              <p className="text-xs text-gray-400 mt-0.5">
                {filtered.length} article{filtered.length !== 1 ? "s" : ""} —
                last 30 days
              </p>
            )}
          </div>
          <Link
            href="/daily-ca"
            className="text-sm text-blue-600 hover:underline font-medium"
          >
            Full Feed →
          </Link>
        </div>
      </div>

      {/* Body */}
      <div className="max-w-[860px] mx-auto py-4 px-4">
        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm mb-4">
            {error}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden divide-y divide-gray-100">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-5 py-4 animate-pulse">
                <div className="flex-1 space-y-2">
                  <div className="h-3.5 bg-gray-100 rounded w-1/4" />
                  <div className="h-4 bg-gray-200 rounded w-3/4" />
                  <div className="h-3 bg-gray-100 rounded w-1/2" />
                </div>
                <div className="w-16 space-y-2 items-end flex flex-col">
                  <div className="h-3 bg-gray-100 rounded w-full" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Articles list */}
        {!loading && !error && filtered.length > 0 && (
          <>
            <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              {filtered.map((article) => (
                <NewsArticleRow key={article.id} article={article} />
              ))}
            </div>

            {/* P2.6 — Load more (only shown when not filtering by category) */}
            {activeCategory === "all" && hasMore && (
              <div className="flex justify-center mt-4">
                <button
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="px-6 py-2.5 rounded-xl bg-white border border-gray-200 text-sm font-medium text-gray-700 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loadingMore ? "Loading…" : "Load 10 more days"}
                </button>
              </div>
            )}
          </>
        )}

        {/* Empty state */}
        {!loading && !error && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <p className="text-4xl mb-4">📰</p>
            <p className="text-gray-600 font-medium mb-1">
              {activeCategory === "all"
                ? "No articles in the last 30 days."
                : `No "${activeCategoryLabel}" articles in the last 30 days.`}
            </p>
            <p className="text-sm text-gray-400 mb-4">
              {activeCategory !== "all" &&
                "Try selecting a different category from the navbar above."}
            </p>
            <Link
              href="/daily-ca"
              className="text-sm text-blue-600 hover:underline font-medium"
            >
              ← View full Daily CA feed
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Default export — wrapped in Suspense for useSearchParams ──────────────────

export default function NewsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50" />}>
      <NewsPageInner />
    </Suspense>
  );
}
