"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { getResearchHistory } from "@/lib/api/research-agent";
import type { HistoryListItem } from "@/types/research_agent";

export interface UseResearchHistoryReturn {
  items: HistoryListItem[];
  isLoading: boolean;
  error: string | null;
  hasNextPage: boolean;
  requiresAuth: boolean;
  loadNextPage: () => void;
  refresh: () => void;
}

export function useResearchHistory(): UseResearchHistoryReturn {
  const { isAuthenticated } = useAuth();

  const [items, setItems] = useState<HistoryListItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [fetchKey, setFetchKey] = useState(0); // increment to force refresh

  const fetchPage = useCallback(async (pageNum: number, replace: boolean) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getResearchHistory(pageNum);
      setItems((prev) => (replace ? data.results : [...prev, ...data.results]));
      setHasNextPage(data.next !== null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load history.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial load / refresh
  useEffect(() => {
    if (!isAuthenticated) return;
    setPage(1);
    setItems([]);
    fetchPage(1, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, fetchKey]);

  // Subsequent pages
  useEffect(() => {
    if (page === 1) return;
    fetchPage(page, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  function loadNextPage() {
    if (!hasNextPage || isLoading) return;
    setPage((prev) => prev + 1);
  }

  function refresh() {
    setFetchKey((k) => k + 1);
  }

  return {
    items,
    isLoading,
    error,
    hasNextPage,
    requiresAuth: !isAuthenticated,
    loadNextPage,
    refresh,
  };
}
