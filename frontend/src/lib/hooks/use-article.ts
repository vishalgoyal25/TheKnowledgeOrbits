/**
 * React Query hooks for articles
 */

"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api/client";
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
    },
  });
}
