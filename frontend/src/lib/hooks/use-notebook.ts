"use client";

import { useQuery } from "@tanstack/react-query";
import { notebookAPI } from "@/lib/api/notebook";

export function useNotebook() {
  return useQuery({
    queryKey: ["notebook"],
    queryFn: notebookAPI.getMyArticles,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}
