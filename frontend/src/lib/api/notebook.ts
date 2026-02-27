import apiClient from "./client";
import { Article } from "@/types/notebook";

export const notebookAPI = {
  // Get user's private articles (My Notebook)
  getMyArticles: async (): Promise<Article[]> => {
    const response = await apiClient.get("/articles/my-notebook/");
    // Handle paginated response
    const results = Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
    return results;
  },

  // Delete article
  deleteArticle: async (articleId: string): Promise<void> => {
    await apiClient.delete(`/articles/${articleId}/`);
  },

  // Generate new article
  generateArticle: async (data: {
    topic_id: string;
    include_ca: boolean;
  }): Promise<Article> => {
    const response = await apiClient.post("/articles/generate/", data);
    return response.data;
  },

  // Get all articles (with optional pagination/filters)
  getArticles: async (params?: Record<string, unknown>): Promise<Article[]> => {
    const response = await apiClient.get("/articles/", { params });
    // Handle paginated response
    return Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
  },
};
