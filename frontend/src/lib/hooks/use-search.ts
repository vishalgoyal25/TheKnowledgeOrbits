/**
 * React Query hooks for search
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import { searchAPI, SearchParams, SearchResult } from "../api/search";

/**
 * useSearch - Custom React Query hook for global semantic search.
 * Triggers unified search across articles, topics, and current affairs.
 */
export function useSearch(params: SearchParams, enabled: boolean = true) {
  return useQuery<SearchResult[]>({
    queryKey: ["search", params],
    queryFn: () => searchAPI.search(params),
    enabled: enabled && !!params.q && params.q.length >= 2,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}
