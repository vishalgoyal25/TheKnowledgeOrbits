/**
 * useInsights Hook - Fetch and manage AI-powered learning insights
 */

"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { analyticsAPI } from "../api/analytics";
import { Insight } from "@/types/dashboard";
import { ApiError } from "@/lib/types";
import { toast } from "@/hooks/use-toast";

/**
 * useInsights - Custom hook for managing AI-powered learning insights.
 * Fetches existing insights from the dashboard and provides a production-ready
 * mutation to trigger re-generation of insights based on latest activity.
 */
export function useInsights() {
  const queryClient = useQueryClient();

  // Query to fetch existing insights by deep-linking into dashboard data
  const query = useQuery<Insight[]>({
    queryKey: ["insights"],
    queryFn: async () => {
      const dashboard = await analyticsAPI.getDashboard();
      return dashboard.insights;
    },
    staleTime: 10 * 60 * 1000, // 10 minutes
  });

  // Mutation to trigger backend AI analysis for new insights
  const generateMutation = useMutation({
    mutationFn: analyticsAPI.generateInsights,
    onSuccess: (newInsights: Insight[]) => {
      // Optimistically update the cache with returned insights
      queryClient.setQueryData(["insights"], newInsights);
      toast({
        title: "Insights Updated",
        description: "AI has successfully analyzed your recent performance.",
      });
    },
    onError: (error: AxiosError<ApiError>) => {
      toast({
        title: "Analysis Failed",
        description: error.response?.data?.message || error.response?.data?.error || "Failed to generate new insights. Please try again later.",
        variant: "destructive",
      });
    },
  });

  return {
    ...query,
    generateInsights: generateMutation.mutate,
    isGenerating: generateMutation.isPending,
  };
}
