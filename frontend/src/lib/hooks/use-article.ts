/**
 * React Query hooks for articles
 */

"use client";

import apiClient from "@/lib/api/client";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { articlesAPI } from "../api/articles";
import {
  Article,
  ArticleFilterParams,
  ArticleGenerationRequest,
} from "../types";

// List articles
export function useArticles(params?: ArticleFilterParams) {
  return useQuery({
    queryKey: ["articles", params],
    queryFn: () => articlesAPI.list(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 min — survive page navigation
  });
}

// Infinite List articles (for Timeline Load More)
export function useInfiniteArticles(params?: ArticleFilterParams) {
  return useInfiniteQuery({
    queryKey: ["articles-infinite", params],
    queryFn: ({ pageParam = 0 }) =>
      articlesAPI.list({ ...params, limit: 20, offset: pageParam as number }),
    getNextPageParam: (lastPage, allPages) => {
      if (lastPage.next) {
        return allPages.length * 20;
      }
      return undefined;
    },
    initialPageParam: 0,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000, // Keep timeline data in memory
  });
}

// Get article by ID
export function useArticle(articleId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["article", articleId],
    queryFn: async () => {
      const response = await apiClient.get<Article>(`/articles/${articleId}/`);
      return response.data;
    },
    enabled: !!articleId && (options?.enabled ?? true),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 60 * 60 * 1000, // 1 hour — article detail is heavy, keep it longer
  });
}

// Get article sources
export function useArticleSources(id: string | null) {
  return useQuery({
    queryKey: ["article-sources", id],
    queryFn: () => articlesAPI.getSources(id!),
    enabled: !!id,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// List articles by topic
export function useArticlesByTopic(
  topicId: string | null,
  params?: ArticleFilterParams,
) {
  return useQuery({
    queryKey: ["articles", "topic", topicId, params],
    queryFn: () => articlesAPI.listByTopic(topicId!, params),
    enabled: !!topicId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to trigger the AI generation of a new article.
 *
 * Submits a RAG-based generation request to the backend and updates
 * the local articles cache upon success.
 */
export function useGenerateArticle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ArticleGenerationRequest) => articlesAPI.generate(data),
    onSuccess: (data) => {
      // Invalidate articles list
      queryClient.invalidateQueries({ queryKey: ["articles"] });

      // Set article in cache
      queryClient.setQueryData(["article", data.article.id], data.article);

      // Invalidate dashboard cache (stats changed)
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
