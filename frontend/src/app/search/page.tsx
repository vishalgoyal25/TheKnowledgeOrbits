/**
 * Search results page
 */

"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useSearch } from "@/lib/hooks/use-search";
import Link from "next/link";
import SearchResults from "@/components/search/search-results";
import ErrorMessage from "@/components/shared/error-message";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Search, FileText, Folder } from "lucide-react";

import { Suspense } from "react";

function SearchPageContent() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";

  const {
    data: results,
    isLoading,
    error,
  } = useSearch({ q: query }, query.length >= 2);

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

      {/* Loading / Error states via SearchResults */}
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
          <div className="mb-6 text-sm text-gray-600">
            Found {results.length} results
            {/* Debug helper: REMOVE IN PRODUCTION */}
            <span className="hidden">{JSON.stringify(results)}</span>
          </div>

          {results.length === 0 ? (
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
            <div className="space-y-4">
              {results.map((result: any) => (
                <Link
                  key={`${result.type}-${result.id}`}
                  href={
                    result.url ||
                    (result.type === "article" ? `/articles/${result.id}` : "#")
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
                        {result.metadata?.source && (
                          <span className="flex items-center gap-1">
                            <span className="font-semibold text-slate-700">
                              Source:
                            </span>{" "}
                            {result.metadata.source}
                          </span>
                        )}
                        {result.metadata?.chapter && (
                          <span className="flex items-center gap-1">
                            <span className="font-semibold text-slate-700">
                              Chapter:
                            </span>{" "}
                            {result.metadata.chapter}
                          </span>
                        )}
                        {result.metadata?.subject && (
                          <span className="flex items-center gap-1">
                            <span className="font-semibold text-slate-700">
                              Subject:
                            </span>{" "}
                            {result.metadata.subject}
                          </span>
                        )}
                        {result.metadata?.date && (
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
