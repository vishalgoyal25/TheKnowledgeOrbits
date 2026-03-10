"use client";

import { useState } from "react";
import CAArticleCard from "@/components/current-affairs/ca-article-card";
import CAFilterBar from "@/components/current-affairs/ca-filter-bar";
import CATimeline from "@/components/current-affairs/ca-timeline";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useCAArticles,
  useInfiniteCAArticles,
} from "@/lib/hooks/use-current-affairs";
import { CAArticleListResponse, CAArticle, CASource } from "@/lib/types";
import {
  ChevronLeft,
  ChevronRight,
  History,
  LayoutGrid,
  Loader2,
  Newspaper,
} from "lucide-react";

interface Props {
  initialArticles: CAArticle[];
  initialTotal: number;
  sources: CASource[];
}

export default function CurrentAffairsClient({ initialArticles, initialTotal, sources }: Props) {
  const [filters, setFilters] = useState({});
  const [gridPage, setGridPage] = useState(1);
  const [activeTab, setActiveTab] = useState("grid");
  const PAGE_SIZE = 20;

  // Grid Query (Numbered Pagination)
  // We use the initialArticles only on page 1 with no filters
  const isInitialState = gridPage === 1 && Object.keys(filters).length === 0;

  const { data: gridData, isLoading: isGridLoading } = useCAArticles({
    ...filters,
    ordering: "-published_at",
    limit: PAGE_SIZE,
    offset: (gridPage - 1) * PAGE_SIZE,
  }, {
    // Skip fetching if we are on the first page with no filters
    enabled: !isInitialState || activeTab !== "grid"
  });

  // Timeline Query (Infinite Scroll / Load More)
  const {
    data: timelineData,
    isLoading: isTimelineLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useInfiniteCAArticles({
    ...filters,
    ordering: "-published_at",
  }, {
    // Only enable when user switches to timeline tab or applies filters
    enabled: activeTab === "timeline" || Object.keys(filters).length > 0
  });

  // Extract arrays
  const gridArticles = isInitialState ? initialArticles : (gridData?.results || []);
  const gridTotal = isInitialState ? initialTotal : (gridData?.count || 0);

  const timelineArticles =
    timelineData?.pages.flatMap(
      (page: CAArticleListResponse) => page.results,
    ) || [];
  const timelineTotal = timelineData?.pages[0]?.count || 0;

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
        pages.push(1, "...", totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages);
      } else {
        pages.push(1, "...", gridPage - 1, gridPage, gridPage + 1, "...", totalPages);
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
            {totalArticles}
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
            {displayArticles.length}
          </div>
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
            <div className="flex justify-center p-12">
              <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
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
                        <span key={`ellipsis-${idx}`} className="px-2 text-gray-500">
                          ...
                        </span>
                      ) : (
                        <Button
                          key={`page-${pageNum}`}
                          variant={gridPage === pageNum ? "default" : "outline"}
                          size="icon"
                          onClick={() => setGridPage(pageNum as number)}
                          className={gridPage === pageNum ? "bg-blue-600 text-white" : ""}
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

              {/* Load More Button */}
              {hasNextPage && (
                <div className="flex justify-center mt-10">
                  <Button
                    variant="outline"
                    size="lg"
                    onClick={() => fetchNextPage()}
                    disabled={isFetchingNextPage}
                    className="min-w-[200px]"
                  >
                    {isFetchingNextPage ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />{" "}
                        Loading...
                      </>
                    ) : (
                      "Load More History"
                    )}
                  </Button>
                </div>
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </>
  );
}
