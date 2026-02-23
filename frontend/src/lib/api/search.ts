/**
 * Search API endpoints
 */

import apiClient from "./client";

export interface SearchParams {
  q: string;
  type?: "articles" | "topics" | "all";
  limit?: number;
}

export interface SearchResult {
  type: "article" | "topic" | "current_affair";
  id: string;
  title: string;
  snippet: string;
  relevance: number;
  url?: string;
  metadata: Record<string, unknown>;
}

export const searchAPI = {
  // UNIFIED SEMANTIC SEARCH
  search: async (params: SearchParams) => {
    const { q, limit = 10 } = params;

    // Call our new Unified Search Endpoint
    const response = await apiClient.get("/knowledge/search/", {
      params: { q, limit },
    });

    // The backend now returns a properly formatted list of results
    // so we can just return it directly.
    return response.data;
  },
};
