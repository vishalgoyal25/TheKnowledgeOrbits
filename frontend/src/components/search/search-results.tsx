"use client";

import { Loader2, SearchX } from "lucide-react";

interface SearchResult {
  id: string;
  title: string;
  description?: string;
  type?: string;
  url?: string;
  meta?: string;
}

interface SearchResultsProps {
  results: SearchResult[];
  isLoading?: boolean;
  query?: string;
  onResultClick?: (result: SearchResult) => void;
  emptyMessage?: string;
}

export default function SearchResults({
  results,
  isLoading = false,
  query = "",
  onResultClick,
  emptyMessage = "No results found.",
}: SearchResultsProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-400">
        <Loader2 className="h-6 w-6 animate-spin mr-2" />
        <span>Searching...</span>
      </div>
    );
  }

  if (!results || results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-400 gap-3">
        <SearchX className="h-10 w-10" />
        <p className="text-sm">
          {query ? `No results for "${query}"` : emptyMessage}
        </p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-gray-100">
      {results.map((result) => (
        <div
          key={result.id}
          onClick={() => onResultClick?.(result)}
          className={`p-4 hover:bg-gray-50 transition-colors ${
            onResultClick ? "cursor-pointer" : ""
          }`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <h4 className="font-medium text-gray-900 truncate">
                {result.title}
              </h4>
              {result.description && (
                <p className="text-sm text-gray-500 mt-0.5 line-clamp-2">
                  {result.description}
                </p>
              )}
              {result.meta && (
                <p className="text-xs text-gray-400 mt-1">{result.meta}</p>
              )}
            </div>
            {result.type && (
              <span className="flex-shrink-0 text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full font-medium capitalize">
                {result.type}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
