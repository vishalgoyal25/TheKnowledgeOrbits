"use client";

import { useState, useCallback, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api/client";
import { debounce } from "lodash";
import { tokenManager } from "@/lib/auth/token-manager";

interface ReadingProgress {
  percent_read: number;
  last_position: number;
}

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
        const response = await apiClient.get(
          `/userstate/reading-progress/${articleId}/`,
        );
        setProgress(response.data);
      } catch (error) {
        // No saved progress or error
        setProgress({ percent_read: 0, last_position: 0 });
      }
    };
    loadProgress();
  }, [articleId]);

  // Debounced API call to save progress
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const saveProgressDebounced = useCallback(
    debounce(async (percent: number, position: number) => {
      if (!tokenManager.getAccessToken()) return;
      try {
        // Normalize values to satisfy backend constraints
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
        console.error("Failed to save reading progress:", error);
      }
    }, 1000),
    [articleId],
  );

  // Immediate UI update + debounced save
  const updateProgress = useCallback(
    (percent: number, position: number) => {
      setProgress({ percent_read: percent, last_position: position });
      saveProgressDebounced(percent, position);
    },
    [saveProgressDebounced],
  );

  return { progress, updateProgress };
}

export function useReadingHistory() {
  return useQuery({
    queryKey: ["reading-history"],
    queryFn: async () => {
      const response = await apiClient.get("/userstate/reading-progress/");
      return response.data;
    },
  });
}
