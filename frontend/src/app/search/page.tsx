/**
 * Search results page — with client-side pagination (20 per page)
 */

"use client";

import { useSearchParams } from "next/navigation";
import { useSearch } from "@/lib/hooks/use-search";
import { useState, useEffect } from "react";
import Link from "next/link";
import SearchResults from "@/components/search/search-results";
import ErrorMessage from "@/components/shared/error-message";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Search,
  FileText,
  Folder,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { SearchResult } from "@/lib/api/search";

import { Suspense } from "react";

const PAGE_SIZE = 20;

function SearchPageContent() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";

  const [currentPage, setCurrentPage] = useState(1);

  // Reset to page 1 whenever the query changes
  useEffect(() => {
    setCurrentPage(1);
  }, [query]);

  const {
    data: results,
    isLoading,
    error,
  } = useSearch({ q: query, limit: 50 }, query.length >= 2);

  if (!query || query.length < 2) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center py-12">
          <Search className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">Enter at least 2 characters to search</p>
        </div>
      </div>
    );
  }

  const totalResults = results?.length ?? 0;
  const totalPages = Math.ceil(totalResults / PAGE_SIZE);
  const paginated = results
    ? results.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
    : [];

  const goToPage = (page: number) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Build page number array with ellipsis: [1, ..., 4, 5, 6, ..., 12]
  const getPageNumbers = (): (number | "...")[] => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    const pages: (number | "...")[] = [1];
    if (currentPage > 3) pages.push("...");
    for (
      let i = Math.max(2, currentPage - 1);
      i <= Math.min(totalPages - 1, currentPage + 1);
      i++
    ) {
      pages.push(i);
    }
    if (currentPage < totalPages - 2) pages.push("...");
    pages.push(totalPages);
    return pages;
  };

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Search Results</h1>
        <p className="text-gray-600">
          Showing results for{" "}
          <span className="font-medium">&quot;{query}&quot;</span>
        </p>
      </div>

      {/* Loading state */}
      {isLoading && (
        <SearchResults results={[]} isLoading={true} query={query} />
      )}

      {/* Error */}
      {error && (
        <ErrorMessage
          title="Search failed"
          message="Could not fetch search results. Please try again."
          onRetry={() => window.location.reload()}
        />
      )}

      {/* Results */}
      {!isLoading && results && (
        <>
          {/* Result count + pagination info */}
          <div className="mb-6 flex items-center justify-between text-sm text-gray-600">
            <span>
              Found{" "}
              <span className="font-semibold text-gray-800">
                {totalResults}
              </span>{" "}
              results
              {totalPages > 1 && (
                <>
                  {" "}
                  — page{" "}
                  <span className="font-semibold text-gray-800">
                    {currentPage}
                  </span>{" "}
                  of{" "}
                  <span className="font-semibold text-gray-800">
                    {totalPages}
                  </span>
                </>
              )}
            </span>
            {totalPages > 1 && (
              <span className="text-xs text-gray-400">
                Showing {(currentPage - 1) * PAGE_SIZE + 1}–
                {Math.min(currentPage * PAGE_SIZE, totalResults)} of{" "}
                {totalResults}
              </span>
            )}
          </div>

          {totalResults === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <Search className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">
                No results found for &quot;{query}&quot;
              </p>
              <p className="text-sm text-gray-500 mt-2">
                Try different keywords or browse topics
              </p>
            </div>
          ) : (
            <>
              {/* Result cards */}
              <div className="space-y-4">
                {paginated.map((result: SearchResult) => (
                  <Link
                    key={`${result.type}-${result.id}`}
                    href={
                      result.url ||
                      (result.type === "article"
                        ? `/articles/${result.id}`
                        : "#")
                    }
                    className="block group"
                  >
                    <Card className="hover:shadow-md transition-shadow border-slate-200">
                      <CardHeader className="pb-2">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              {result.type === "article" && (
                                <FileText className="h-4 w-4 text-blue-500" />
                              )}
                              {result.type === "topic" && (
                                <Folder className="h-4 w-4 text-purple-500" />
                              )}
                              {result.type === "current_affair" && (
                                <div className="h-4 w-4 rounded-full bg-emerald-500" />
                              )}

                              <Badge
                                variant={
                                  result.type === "topic"
                                    ? "default"
                                    : result.type === "current_affair"
                                      ? "secondary"
                                      : "outline"
                                }
                                className="uppercase text-[10px] tracking-wider"
                              >
                                {result.type.replace("_", " ")}
                              </Badge>
                            </div>

                            <CardTitle className="text-lg font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                              {result.title}
                            </CardTitle>
                          </div>
                        </div>
                      </CardHeader>

                      <CardContent>
                        <p className="text-sm text-slate-600 line-clamp-2 leading-relaxed">
                          {result.snippet}
                        </p>

                        <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-500 border-t pt-3">
                          {typeof result.metadata?.source === "string" && (
                            <span className="flex items-center gap-1">
                              <span className="font-semibold text-slate-700">
                                Source:
                              </span>{" "}
                              {result.metadata.source}
                            </span>
                          )}
                          {typeof result.metadata?.chapter === "string" && (
                            <span className="flex items-center gap-1">
                              <span className="font-semibold text-slate-700">
                                Chapter:
                              </span>{" "}
                              {result.metadata.chapter}
                            </span>
                          )}
                          {typeof result.metadata?.subject === "string" && (
                            <span className="flex items-center gap-1">
                              <span className="font-semibold text-slate-700">
                                Subject:
                              </span>{" "}
                              {result.metadata.subject}
                            </span>
                          )}
                          {typeof result.metadata?.date === "string" && (
                            <span className="flex items-center gap-1">
                              <span className="font-semibold text-slate-700">
                                Date:
                              </span>{" "}
                              {result.metadata.date}
                            </span>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>

              {/* Pagination — only shown when there is more than 1 page */}
              {totalPages > 1 && (
                <div className="mt-10 flex items-center justify-center gap-1">
                  {/* Prev */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => goToPage(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="h-9 w-9 p-0"
                    aria-label="Previous page"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>

                  {/* Page numbers */}
                  {getPageNumbers().map((page, idx) =>
                    page === "..." ? (
                      <span
                        key={`ellipsis-${idx}`}
                        className="h-9 w-9 flex items-center justify-center text-sm text-gray-400 select-none"
                      >
                        …
                      </span>
                    ) : (
                      <Button
                        key={page}
                        variant={currentPage === page ? "default" : "outline"}
                        size="sm"
                        onClick={() => goToPage(page as number)}
                        className="h-9 w-9 p-0 text-sm"
                        aria-label={`Page ${page}`}
                        aria-current={currentPage === page ? "page" : undefined}
                      >
                        {page}
                      </Button>
                    ),
                  )}

                  {/* Next */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => goToPage(currentPage + 1)}
                    disabled={currentPage === totalPages}
                    className="h-9 w-9 p-0"
                    aria-label="Next page"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="container mx-auto px-4 py-8 text-center text-gray-500">
          Loading search...
        </div>
      }
    >
      <SearchPageContent />
    </Suspense>
  );
}
