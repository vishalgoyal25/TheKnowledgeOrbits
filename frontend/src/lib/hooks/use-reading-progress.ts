"use client";

import { useState, useCallback, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api/client";
import { debounce } from "lodash";
import { tokenManager } from "@/lib/auth/token-manager";
import { createLogger } from "@/lib/logger";

const logger = createLogger("ReadingProgress");

export interface ReadingProgress {
  percent_read: number;
  last_position: number;
}

/**
 * Interface for reading history records returning from the API.
 */
export interface ReadingHistoryItem extends ReadingProgress {
  id: string;
  article_id: string;
  article_title: string;
  topic_name: string;
  created_at: string;
  updated_at: string;
}

/**
 * useReadingProgress - Hook to sync real-time reading progress for a specific article.
 * Automatically saves progress on scroll with a debounce.
 */
export function useReadingProgress(articleId: string) {
  const [progress, setProgress] = useState<ReadingProgress | null>(null);

  // Load saved progress
  useEffect(() => {
    const loadProgress = async () => {
      if (!tokenManager.getAccessToken()) {
        setProgress({ percent_read: 0, last_position: 0 });
        return;
      }
      try {
        const response = await apiClient.get<ReadingProgress>(
          `/userstate/reading-progress/${articleId}/`,
        );
        setProgress(response.data);
      } catch (error) {
        // No saved progress or error defaults to start
        setProgress({ percent_read: 0, last_position: 0 });
      }
    };
    loadProgress();
  }, [articleId]);

  // Debounced API call to save progress to prevent spamming the backend
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const saveProgressDebounced = useCallback(
    debounce(async (percent: number, position: number) => {
      if (!tokenManager.getAccessToken()) return;
      try {
        // Normalize values to satisfy backend constraints (0-100)
        const safePercent = Math.min(100, Math.max(0, percent));
        const safePosition = Math.round(position);

        await apiClient.put(
          `/userstate/reading-progress/${articleId}/update/`,
          {
            percent_read: safePercent,
            last_position: safePosition,
          },
        );
      } catch (error) {
        logger.error("Failed to save reading progress:", error);
      }
    }, 1000),
    [articleId],
  );

  /**
   * Updates local state immediately and triggers a debounced save to the cloud.
   */
  const updateProgress = useCallback(
    (percent: number, position: number) => {
      setProgress({ percent_read: percent, last_position: position });
      saveProgressDebounced(percent, position);
    },
    [saveProgressDebounced],
  );

  return { progress, updateProgress };
}

/**
 * useReadingHistory - Hook to fetch all recent reading activities across the app.
 */
export function useReadingHistory() {
  return useQuery<ReadingHistoryItem[]>({
    queryKey: ["reading-history"],
    queryFn: async () => {
      const response = await apiClient.get<ReadingHistoryItem[]>("/userstate/reading-progress/");
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
