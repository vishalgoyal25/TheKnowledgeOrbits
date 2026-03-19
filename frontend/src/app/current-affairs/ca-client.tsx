"use client";

import { useEffect, useRef, useState } from "react";
import CAArticleCard from "@/components/current-affairs/ca-article-card";
import CAFilterBar from "@/components/current-affairs/ca-filter-bar";
import CATimeline from "@/components/current-affairs/ca-timeline";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Link from "next/link";
import {
  useCAArticles,
  useInfiniteCAArticles,
} from "@/lib/hooks/use-current-affairs";
import { CAArticleListResponse, CAArticle, CASource } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ChevronLeft,
  ChevronRight,
  History,
  LayoutGrid,
  Loader2,
  Newspaper,
  Scale,
} from "lucide-react";

interface Props {
  initialArticles: CAArticle[];
  initialTotal: number;
  sources: CASource[];
}

export default function CurrentAffairsClient({
  initialArticles,
  initialTotal,
  sources,
}: Props) {
  const [filters, setFilters] = useState({});
  const [gridPage, setGridPage] = useState(1);
  const [activeTab, setActiveTab] = useState("grid");
  const PAGE_SIZE = 20;

  // Grid Query (Numbered Pagination)
  // We use the initialArticles only on page 1 with no filters AND if we actually have initial data
  const isInitialState =
    gridPage === 1 &&
    Object.keys(filters).length === 0 &&
    initialArticles.length > 0;

  const { data: gridData, isLoading: isGridLoading } = useCAArticles(
    {
      ...filters,
      ordering: "-published_at",
      limit: PAGE_SIZE,
      offset: (gridPage - 1) * PAGE_SIZE,
    },
    {
      // Skip fetching if we are on the first page with no filters
      enabled: !isInitialState || activeTab !== "grid",
    },
  );

  // Timeline Query (Infinite Scroll / Load More)
  const {
    data: timelineData,
    isLoading: isTimelineLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useInfiniteCAArticles(
    {
      ...filters,
      ordering: "-published_at",
    },
    {
      // Only enable when user switches to timeline tab or applies filters
      enabled: activeTab === "timeline" || Object.keys(filters).length > 0,
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

  // Extract arrays, retaining initial data during first-load to prevent "disappearing" content
  const gridArticles = gridData?.results?.length
    ? gridData.results
    : isInitialState || isGridLoading
      ? initialArticles
      : [];
  const gridTotal =
    gridData?.count ?? (isInitialState || isGridLoading ? initialTotal : 0);

  const timelineArticles =
    timelineData?.pages.flatMap(
      (page: CAArticleListResponse) => page.results,
    ) || (isTimelineLoading ? initialArticles : []);
  const timelineTotal =
    timelineData?.pages[0]?.count ?? (isTimelineLoading ? initialTotal : 0);

  const totalArticles = activeTab === "grid" ? gridTotal : timelineTotal;
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
            {totalArticles === 0 && (isGridLoading || isTimelineLoading) ? (
              <Loader2 className="h-8 w-8 animate-spin inline-block" />
            ) : (
              totalArticles
            )}
          </div>
        </div>

        <div className="bg-green-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Active Sources</div>
          <div className="text-3xl font-bold text-green-600">
            {sources.filter((s) => s.is_active).length}
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

      {/* Educational & Legal Disclaimer Banner (Prominent Notice) */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-8 flex items-start gap-4">
        <div className="h-10 w-10 shrink-0 bg-amber-100 rounded-lg flex items-center justify-center text-amber-600">
          <Scale className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <h4 className="text-sm font-bold text-amber-900 uppercase tracking-wider mb-1">
            Educational Notice & Terms
          </h4>
          <p className="text-xs text-amber-800 leading-relaxed">
            TheKnowledgeOrbits is a{" "}
            <strong>non-commercial hobby project</strong> for technical
            learning. Content is synthesized from public news for academic
            dissemination. By continuing, you acknowledge our{" "}
            <Link
              href="/terms"
              className="underline font-bold hover:text-amber-600"
            >
              Terms of Service
            </Link>
            ,{" "}
            <Link
              href="/privacy"
              className="underline font-bold hover:text-amber-600"
            >
              Privacy Policy
            </Link>
            , and{" "}
            <Link
              href="/cookies"
              className="underline font-bold hover:text-amber-600"
            >
              Cookie Policy
            </Link>
            . We prioritize source attribution and encourage reading original
            coverage.
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-8">
        <CAFilterBar
          onFilterChange={(newFilters) => {
            setFilters(newFilters);
            setGridPage(1);
          }}
          sources={sources.map((s) => ({ id: s.id, name: s.name }))}
        />
      </div>

      {/* Views */}
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
                  <Skeleton className="h-4 w-1/4 rounded-full" />
                  <Skeleton className="h-24 w-full rounded-lg" />
                  <div className="space-y-2">
                    <Skeleton className="h-3 w-full rounded-full" />
                    <Skeleton className="h-3 w-3/4 rounded-full" />
                  </div>
                  <div className="pt-4 flex justify-between">
                    <Skeleton className="h-8 w-20 rounded-md" />
                  </div>
                </div>
              ))}
            </div>
          ) : gridArticles.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <Newspaper className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">No articles found on this page</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
                {gridArticles.map((article) => (
                  <CAArticleCard key={article.id} article={article} />
                ))}
              </div>

              {/* Standard Page Paginator */}
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

        <TabsContent value="timeline" className="mt-6">
          {timelineArticles.length === 0 && !isTimelineLoading ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <History className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">No articles found</p>
            </div>
          ) : (
            <div className="pb-12">
              <CATimeline articles={timelineArticles} />

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
