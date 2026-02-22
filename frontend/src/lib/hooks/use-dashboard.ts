"use client";

import { useQuery } from "@tanstack/react-query";
import { analyticsAPI } from "@/lib/api/analytics";

export function useDashboard(enabled = true) {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: analyticsAPI.getDashboard,
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
