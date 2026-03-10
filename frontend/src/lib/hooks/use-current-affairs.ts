/**
 * React Query hooks for Current Affairs
 */

"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import {
  CAArticleFilterParams,
  CAChunkFilterParams,
  currentAffairsAPI,
} from "../api/current-affairs";

// List CA sources
export function useCASources() {
  return useQuery({
    queryKey: ["ca-sources"],
    queryFn: () => currentAffairsAPI.listSources(),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// Get CA source
export function useCASource(id: string | null) {
  return useQuery({
    queryKey: ["ca-source", id],
    queryFn: () => currentAffairsAPI.getSource(id!),
    enabled: !!id,
    staleTime: 10 * 60 * 1000,
  });
}

// List CA articles
export function useCAArticles(
  params?: CAArticleFilterParams,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ["ca-articles", params],
    queryFn: () => currentAffairsAPI.listArticles(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 min — survive page navigation
    ...options,
  });
}

// Infinite List CA articles (for Timeline Load More)
export function useInfiniteCAArticles(
  params?: CAArticleFilterParams,
  options?: { enabled?: boolean },
) {
  return useInfiniteQuery({
    queryKey: ["ca-articles-infinite", params],
    queryFn: ({ pageParam = 0 }) =>
      currentAffairsAPI.listArticles({
        ...params,
        limit: 20,
        offset: pageParam as number,
      }),
    getNextPageParam: (lastPage, allPages) => {
      if (lastPage.next) {
        return allPages.length * 20;
      }
      return undefined;
    },
    initialPageParam: 0,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000, // Keep timeline data in memory
    ...options,
  });
}

// Get CA article
export function useCAArticle(id: string | null) {
  return useQuery({
    queryKey: ["ca-article", id],
    queryFn: () => currentAffairsAPI.getArticle(id!),
    enabled: !!id,
    staleTime: 10 * 60 * 1000,
    gcTime: 60 * 60 * 1000, // 1 hour — article detail is heavy, keep it longer
  });
}

// List CA chunks
export function useCAChunks(params?: CAChunkFilterParams) {
  return useQuery({
    queryKey: ["ca-chunks", params],
    queryFn: () => currentAffairsAPI.listChunks(params),
    staleTime: 5 * 60 * 1000,
  });
}

// Get recent CA chunks
export function useRecentCAChunks() {
  return useQuery({
    queryKey: ["ca-chunks", "recent"],
    queryFn: () => currentAffairsAPI.getRecentChunks(),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

// Get CA chunks for topic
export function useCAChunksForTopic(topicId: string | null, days: number = 30) {
  return useQuery({
    queryKey: ["ca-chunks", "topic", topicId, days],
    queryFn: () => currentAffairsAPI.getChunksForTopic(topicId!, days),
    enabled: !!topicId,
    staleTime: 5 * 60 * 1000,
  });
}

// List CA topic links
export function useCATopicLinks(params?: {
  topic_id?: string;
  link_method?: string;
}) {
  return useQuery({
    queryKey: ["ca-topic-links", params],
    queryFn: () => currentAffairsAPI.listTopicLinks(params),
    staleTime: 5 * 60 * 1000,
  });
}
