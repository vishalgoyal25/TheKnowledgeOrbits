"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getAllArticleDetails,
  getTodayArticles,
  getArticlesByDate,
  DailyCaArticleDetail,
} from "@/lib/api/daily-ca";
import { LeftPanel } from "./left-panel";
import { RightPanel } from "./right-panel";
import { DailyCaArticle } from "./daily-ca-article";

/**
 * DailyCaFeed — one-article-at-a-time layout.
 *
 * Left panel lists all 10 articles; clicking one or using Prev/Next swaps
 * the single article shown in the centre column. No continuous scroll.
 */

interface Props {
  date?: string;
}

function todayStr(): string {
  return new Date().toISOString().split("T")[0];
}

export function DailyCaFeed({ date }: Props) {
  const effectiveDate = date ?? todayStr();

  const [articles, setArticles] = useState<DailyCaArticleDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [leftCollapsed, setLeftCollapsed] = useState(false);

  const mainScrollRef = useRef<HTMLDivElement | null>(null);

  // ── Fetch ───────────────────────────────────────────────────────────────────

  const fetchFeed = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const listData = date
        ? await getArticlesByDate(date)
        : await getTodayArticles();

      if (listData.articles.length === 0) {
        setArticles([]);
        return;
      }

      const slugs = listData.articles.map((a) => a.slug);
      const details = await getAllArticleDetails(slugs);
      details.sort((a, b) => a.order_on_date - b.order_on_date);
      setArticles(details);
      if (details.length > 0) setActiveId(details[0].id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load articles");
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => {
    fetchFeed();
  }, [fetchFeed]);

  // ── Scroll to top of centre column when article changes ─────────────────────

  useEffect(() => {
    if (mainScrollRef.current) {
      mainScrollRef.current.scrollTo({ top: 0, behavior: "instant" });
    }
  }, [activeId]);

  // ── Navigation helpers ──────────────────────────────────────────────────────

  const handleArticleClick = (id: string) => {
    setActiveId(id);
  };

  // Derived active article + index (used both for render and right panel)
  const activeIndex = articles.findIndex((a) => a.id === activeId);
  const displayIndex = activeIndex >= 0 ? activeIndex : 0;
  const activeArticle = articles[displayIndex] ?? null;

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div
      className="flex flex-col bg-gray-50"
      style={{ height: "calc(100vh - 0px)" }}
    >
      {/* Top bar — fixed height ~53px */}
      <div className="flex-shrink-0 z-20 bg-white border-b border-gray-200">
        <div className="max-w-[1400px] mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-base font-bold text-gray-900">
              Daily Current Affairs
            </span>
            {!loading && (
              <span className="text-xs text-gray-400">
                {articles.length} article{articles.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
          <button
            onClick={() => setLeftCollapsed((v) => !v)}
            title={leftCollapsed ? "Show contents" : "Hide contents"}
            className="text-gray-400 hover:text-gray-700 transition-colors p-1.5 rounded-lg hover:bg-gray-100"
          >
            {leftCollapsed ? (
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            ) : (
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Body — fills remaining height, columns scroll independently */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {/* Error */}
        {error && (
          <div className="px-4 py-3">
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
              {error}
            </div>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="h-full overflow-y-auto px-4 py-6">
            <div
              className={`grid gap-6 ${
                leftCollapsed
                  ? "grid-cols-1 xl:grid-cols-[1fr_300px]"
                  : "grid-cols-1 lg:grid-cols-[240px_1fr] xl:grid-cols-[260px_1fr_300px]"
              }`}
            >
              <div className="hidden lg:block space-y-3">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-16 bg-gray-200 rounded-xl animate-pulse"
                  />
                ))}
              </div>
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="bg-white rounded-2xl border border-gray-200 p-6 space-y-3"
                  >
                    <div className="h-4 bg-gray-200 rounded animate-pulse w-1/3" />
                    <div className="h-6 bg-gray-200 rounded animate-pulse" />
                    <div className="h-4 bg-gray-100 rounded animate-pulse w-3/4" />
                    <div className="h-4 bg-gray-100 rounded animate-pulse" />
                  </div>
                ))}
              </div>
              <div className="hidden xl:block space-y-3">
                <div className="h-48 bg-gray-200 rounded-xl animate-pulse" />
                <div className="h-32 bg-gray-200 rounded-xl animate-pulse" />
              </div>
            </div>
          </div>
        )}

        {/* Content — app-shell: columns own their scroll */}
        {!loading && !error && (
          <>
            {articles.length === 0 ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <p className="text-4xl mb-4">📰</p>
                  <p className="text-gray-600 font-medium mb-1">
                    No articles for this date
                  </p>
                  <p className="text-sm text-gray-400">
                    Check another date or generate articles from the admin
                    panel.
                  </p>
                </div>
              </div>
            ) : (
              <>
                {/* ── Mobile article strip (< lg) ──────────────────────────────
                    Replaces the left sidebar on phones/small tablets.
                    Horizontally scrollable numbered buttons — tap any to jump.
                    Shown/hidden by the same toggle button as the sidebar.       */}
                {!leftCollapsed && (
                  <div className="lg:hidden flex-shrink-0 bg-white border-b border-gray-200 overflow-x-auto">
                    <div className="flex items-center gap-2 px-4 py-2.5 w-max">
                      {articles.map((article, index) => {
                        const isActive = article.id === activeId;
                        return (
                          <button
                            key={article.id}
                            onClick={() => handleArticleClick(article.id)}
                            title={article.title}
                            className={`flex-shrink-0 w-8 h-8 rounded-full text-xs font-bold transition-colors ${
                              isActive
                                ? "bg-blue-500 text-white shadow-sm"
                                : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                            }`}
                          >
                            {index + 1}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div
                  className={`flex-1 overflow-hidden grid ${
                    leftCollapsed
                      ? "grid-cols-1 xl:grid-cols-[1fr_280px]"
                      : "grid-cols-1 lg:grid-cols-[220px_1fr] xl:grid-cols-[220px_1fr_280px]"
                  }`}
                >
                  {/* Left panel — scrolls independently */}
                  {!leftCollapsed && (
                    <div className="hidden lg:flex flex-col h-full overflow-y-auto border-r border-gray-200 bg-white p-4 gap-4">
                      <LeftPanel
                        articles={articles}
                        activeId={activeId}
                        date={effectiveDate}
                        onArticleClick={handleArticleClick}
                      />
                    </div>
                  )}

                  {/* Main — one article at a time, scrolls independently */}
                  <div ref={mainScrollRef} className="h-full overflow-y-auto">
                    <div className="px-4 py-6">
                      {activeArticle && (
                        <DailyCaArticle
                          article={activeArticle}
                          index={displayIndex}
                          total={articles.length}
                          isActive={true}
                          onPrev={
                            displayIndex > 0
                              ? () =>
                                  handleArticleClick(
                                    articles[displayIndex - 1].id,
                                  )
                              : null
                          }
                          onNext={
                            displayIndex < articles.length - 1
                              ? () =>
                                  handleArticleClick(
                                    articles[displayIndex + 1].id,
                                  )
                              : null
                          }
                        />
                      )}
                    </div>
                  </div>

                  {/* Right panel — scrolls independently */}
                  <div className="hidden xl:flex flex-col h-full overflow-y-auto border-l border-gray-200 bg-white p-4">
                    <RightPanel article={activeArticle} />
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
