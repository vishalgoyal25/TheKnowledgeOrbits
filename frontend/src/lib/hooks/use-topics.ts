/**
 * React Query hooks for topics
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import { topicsAPI } from "../api/topics";
import { PaginationParams } from "../types";

// List all topics
export function useTopics(params?: PaginationParams) {
  return useQuery({
    queryKey: ["topics", params],
    queryFn: () => topicsAPI.list(params),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// Get topic by ID
export function useTopic(id: string | null) {
  return useQuery({
    queryKey: ["topic", id],
    queryFn: () => topicsAPI.getById(id!),
    enabled: !!id,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// List topics by module
export function useTopicsByModule(
  moduleId: string | null,
  params?: PaginationParams,
) {
  return useQuery({
    queryKey: ["topics", "module", moduleId, params],
    queryFn: () => topicsAPI.listByModule(moduleId!, params),
    enabled: !!moduleId,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}
