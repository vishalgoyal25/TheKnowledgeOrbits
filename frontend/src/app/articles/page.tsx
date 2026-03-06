/**
 * Article listing page
 */

"use client";

import ArticleCard from "@/components/articles/article-card";
import ArticleTimeline from "@/components/articles/article-timeline";
import SearchBar from "@/components/search/search-bar";
import SearchFilters from "@/components/search/search-filters";
import EmptyState from "@/components/shared/empty-state";
import ErrorMessage from "@/components/shared/error-message";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useArticles, useInfiniteArticles } from "@/lib/hooks/use-article";
import {
  ChevronLeft,
  ChevronRight,
  History,
  LayoutGrid,
  Loader2,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

export default function ArticlesPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [activeFilters, setActiveFilters] = useState<string[]>([]);

  const filterOptions = [
    { label: "Approved", value: "approved" },
    { label: "Pending", value: "pending" },
    { label: "AI Generated", value: "ai_generated" },
  ];

  const filterStatus =
    activeFilters.find((f) => ["approved", "pending"].includes(f)) || "";

  const [gridPage, setGridPage] = useState(1);
  const [activeTab, setActiveTab] = useState("grid");
  const PAGE_SIZE = 20;

  const {
    data: gridData,
    isLoading: isGridLoading,
    error,
  } = useArticles({
    review_status: filterStatus || undefined,
    ordering: "-created_at",
    limit: PAGE_SIZE,
    offset: (gridPage - 1) * PAGE_SIZE,
  });

  const {
    data: timelineData,
    isLoading: isTimelineLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useInfiniteArticles({
    review_status: filterStatus || undefined,
    ordering: "-created_at",
  });

  // Extract arrays
  const gridArticles = gridData?.results || [];
  const gridTotal = gridData?.count || 0;

  const timelineArticles =
    timelineData?.pages.flatMap((page) => page.results) || [];
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

  if (isGridLoading && isTimelineLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <ErrorMessage
          title="Failed to load articles"
          message="Could not fetch articles. Please check your connection and try again."
          onRetry={() => window.location.reload()}
        />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Articles</h1>
        <p className="text-gray-600">
          Browse AI-generated articles on UPSC topics
        </p>
      </div>

      {/* Search & Filters */}
      <div className="mb-6 space-y-3">
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

      <div className="mb-6 text-sm text-gray-600">
        Showing {displayArticles.length} of {totalArticles} articles
      </div>

      <Tabs defaultValue="grid" className="w-full" onValueChange={setActiveTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="grid" className="gap-2">
            <LayoutGrid className="h-4 w-4" />
            Grid
          </TabsTrigger>
          <TabsTrigger value="timeline" className="gap-2">
            <History className="h-4 w-4" />
            Timeline
          </TabsTrigger>
        </TabsList>

        <TabsContent value="grid">
          {displayArticles.length === 0 ? (
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
          {displayArticles.length === 0 && !isTimelineLoading ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <History className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">No events found in timeline</p>
            </div>
          ) : (
            <div className="pb-12">
              <ArticleTimeline articles={displayArticles} />

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
    </div>
  );
}
