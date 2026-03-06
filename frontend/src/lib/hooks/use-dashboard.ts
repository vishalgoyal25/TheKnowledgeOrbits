"use client";

import { analyticsAPI } from "@/lib/api/analytics";
import { useQuery } from "@tanstack/react-query";

export function useDashboard(enabled = true) {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: analyticsAPI.getDashboard,
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 min — survive page navigation
  });
}
