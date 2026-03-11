"use client";

import { useEffect, useRef, useState } from "react";
import ArticleCard from "@/components/articles/article-card";
import ArticleTimeline from "@/components/articles/article-timeline";
import SearchBar from "@/components/search/search-bar";
import SearchFilters from "@/components/search/search-filters";
import EmptyState from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useArticles, useInfiniteArticles } from "@/lib/hooks/use-article";
import { useAuth } from "@/lib/auth/useAuth";
import {
  ChevronLeft,
  ChevronRight,
  History,
  LayoutGrid,
  Loader2,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { Article } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

interface ArticlesClientProps {
  initialArticles: Article[];
  initialTotal: number;
}

export default function ArticlesClient({
  initialArticles,
  initialTotal,
}: ArticlesClientProps) {
  const { isAuthenticated } = useAuth();
  const [searchTerm, setSearchTerm] = useState("");
  const [activeFilters, setActiveFilters] = useState<string[]>([]);
  const [gridPage, setGridPage] = useState(1);
  const [activeTab, setActiveTab] = useState("grid");
  const PAGE_SIZE = 20;

  const filterOptions = [
    { label: "Approved", value: "approved" },
    { label: "Pending", value: "pending" },
    { label: "AI Generated", value: "ai_generated" },
  ];

  const filterStatus =
    activeFilters.find((f) => ["approved", "pending"].includes(f)) || "";

  // Check if we can use server-side initial data
  // (If initialArticles is empty, we MUST fetch on client even if filters are empty)
  const isInitialState =
    gridPage === 1 &&
    Object.keys(activeFilters).length === 0 &&
    searchTerm === "" &&
    initialArticles.length > 0;

  // If authenticated, we MUST bypass the public server snapshot and fetch fresh private+public data
  const canUseInitialServerState = isInitialState && !isAuthenticated;

  const { data: gridData, isLoading: isGridLoading } = useArticles(
    {
      review_status: filterStatus || undefined,
      ordering: "-created_at",
      limit: PAGE_SIZE,
      offset: (gridPage - 1) * PAGE_SIZE,
    },
    {
      // Only fetch on client if we've deviated from the initial server state or we need private data
      enabled: !canUseInitialServerState || activeTab !== "grid",
    },
  );

  const {
    data: timelineData,
    isLoading: isTimelineLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useInfiniteArticles(
    {
      review_status: filterStatus || undefined,
      ordering: "-created_at",
    },
    {
      enabled: activeTab === "timeline" || !canUseInitialServerState,
    },
  );

  const observerTarget = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { threshold: 0.1 },
    );

    if (observerTarget.current) {
      observer.observe(observerTarget.current);
    }

    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Extract arrays, falling back to initial data if available and in initial state
  // We keep the initial data while loading to avoid the "disappearing" effect
  const gridArticles =
    gridData?.results !== undefined
      ? gridData.results
      : canUseInitialServerState || (isInitialState && isGridLoading)
        ? initialArticles
        : [];
  const gridTotal =
    gridData?.count ??
    (canUseInitialServerState || (isInitialState && isGridLoading)
      ? initialTotal
      : 0);

  const timelineArticles =
    timelineData?.pages.flatMap((page) => page.results) ||
    (isTimelineLoading || canUseInitialServerState ? initialArticles : []);
  const timelineTotal =
    timelineData?.pages[0]?.count ??
    (isTimelineLoading || canUseInitialServerState ? initialTotal : 0);

  const totalArticlesCount = activeTab === "grid" ? gridTotal : timelineTotal;
  const displayArticles =
    activeTab === "grid" ? gridArticles : timelineArticles;

  const totalPages = Math.ceil(gridTotal / PAGE_SIZE);

  const getPageNumbers = () => {
    const pages = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      if (gridPage <= 4) {
        pages.push(1, 2, 3, 4, 5, "...", totalPages);
      } else if (gridPage > totalPages - 4) {
        pages.push(
          1,
          "...",
          totalPages - 4,
          totalPages - 3,
          totalPages - 2,
          totalPages - 1,
          totalPages,
        );
      } else {
        pages.push(
          1,
          "...",
          gridPage - 1,
          gridPage,
          gridPage + 1,
          "...",
          totalPages,
        );
      }
    }
    return pages;
  };

  return (
    <>
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-blue-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Total Articles</div>
          <div className="text-3xl font-bold text-blue-600">
            {totalArticlesCount === 0 &&
            (isGridLoading || isTimelineLoading) ? (
              <Loader2 className="h-8 w-8 animate-spin inline-block" />
            ) : (
              totalArticlesCount
            )}
          </div>
        </div>

        <div className="bg-green-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Sync Capacity</div>
          <div className="text-3xl font-bold text-green-600">
            {initialArticles.length > 0 ? "LIVE" : "SYNC"}
          </div>
        </div>

        <div className="bg-purple-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Showing</div>
          <div className="text-3xl font-bold text-purple-600">
            {displayArticles.length === 0 &&
            (isGridLoading || isTimelineLoading) ? (
              <Loader2 className="h-8 w-8 animate-spin inline-block" />
            ) : (
              displayArticles.length
            )}
          </div>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="mb-8 space-y-4">
        <SearchBar
          placeholder="Search articles..."
          onSearch={setSearchTerm}
          defaultValue={searchTerm}
        />
        <SearchFilters
          filters={filterOptions}
          activeFilters={activeFilters}
          onFilterToggle={(val) => {
            setActiveFilters((prev) =>
              prev.includes(val)
                ? prev.filter((f) => f !== val)
                : [...prev, val],
            );
            setGridPage(1); // Reset page on filter
          }}
          onClearAll={() => {
            setActiveFilters([]);
            setGridPage(1);
          }}
          label="Filter"
        />
      </div>

      <Tabs defaultValue="grid" className="w-full" onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="grid" className="gap-2">
            <LayoutGrid className="h-4 w-4" />
            Grid
          </TabsTrigger>
          <TabsTrigger value="timeline" className="gap-2">
            <History className="h-4 w-4" />
            Timeline
          </TabsTrigger>
        </TabsList>

        <TabsContent value="grid" className="mt-6">
          {isGridLoading && !isInitialState ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
              {[...Array(6)].map((_, i) => (
                <div
                  key={i}
                  className="bg-white rounded-xl border border-gray-100 p-5 space-y-4 shadow-sm"
                >
                  <Skeleton className="h-4 w-1/3 rounded-full" />
                  <Skeleton className="h-20 w-full rounded-lg" />
                  <div className="space-y-2">
                    <Skeleton className="h-3 w-full rounded-full" />
                    <Skeleton className="h-3 w-4/5 rounded-full" />
                  </div>
                  <div className="pt-4 flex justify-between">
                    <Skeleton className="h-8 w-24 rounded-md" />
                  </div>
                </div>
              ))}
            </div>
          ) : displayArticles.length === 0 ? (
            <EmptyState
              title="No articles found"
              description={
                searchTerm
                  ? `No articles match "${searchTerm}". Try a different search.`
                  : "No articles yet. Generate your first article to get started."
              }
              icon={<Sparkles className="h-8 w-8" />}
              action={
                !searchTerm ? (
                  <Link href="/generate">
                    <Button className="gap-2">
                      <Sparkles className="h-4 w-4" />
                      Generate Article
                    </Button>
                  </Link>
                ) : undefined
              }
            />
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
                {displayArticles.map((article) => (
                  <ArticleCard key={article.id} article={article} />
                ))}
              </div>

              {/* Grid Paginator */}
              {gridTotal > PAGE_SIZE && (
                <div className="flex items-center justify-between border-t pt-6 mb-12">
                  <div className="text-sm text-gray-500">
                    Showing{" "}
                    <span className="font-semibold">
                      {(gridPage - 1) * PAGE_SIZE + 1}
                    </span>{" "}
                    to{" "}
                    <span className="font-semibold">
                      {Math.min(gridPage * PAGE_SIZE, gridTotal)}
                    </span>{" "}
                    of <span className="font-semibold">{gridTotal}</span>{" "}
                    articles
                  </div>

                  <div className="flex items-center gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setGridPage((p) => Math.max(1, p - 1))}
                      disabled={gridPage === 1}
                      className="gap-1 mr-2"
                    >
                      <ChevronLeft className="h-4 w-4" /> Prev
                    </Button>

                    {getPageNumbers().map((pageNum, idx) =>
                      pageNum === "..." ? (
                        <span
                          key={`ellipsis-${idx}`}
                          className="px-2 text-gray-500"
                        >
                          ...
                        </span>
                      ) : (
                        <Button
                          key={`page-${pageNum}`}
                          variant={gridPage === pageNum ? "default" : "outline"}
                          size="icon"
                          onClick={() => setGridPage(pageNum as number)}
                          className={
                            gridPage === pageNum ? "bg-blue-600 text-white" : ""
                          }
                        >
                          {pageNum}
                        </Button>
                      ),
                    )}

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setGridPage((p) => p + 1)}
                      disabled={gridPage * PAGE_SIZE >= gridTotal}
                      className="gap-1 ml-2"
                    >
                      Next <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </TabsContent>

        <TabsContent value="timeline">
          {isTimelineLoading && timelineArticles.length === 0 ? (
            <div className="space-y-6">
              {[...Array(3)].map((_, i) => (
                <div
                  key={i}
                  className="h-40 bg-gray-100 animate-pulse rounded-xl"
                />
              ))}
            </div>
          ) : displayArticles.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <History className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">No events found in timeline</p>
            </div>
          ) : (
            <div className="pb-12">
              <ArticleTimeline articles={displayArticles} />

              {/* Infinite Scroll Trigger */}
              {hasNextPage && (
                <div
                  ref={observerTarget}
                  className="flex justify-center mt-10 py-5"
                >
                  {isFetchingNextPage && (
                    <div className="flex items-center text-gray-500 font-medium">
                      <Loader2 className="mr-2 h-5 w-5 animate-spin text-blue-500" />
                      Loading deeper history...
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </>
  );
}
