/**
 * Topics API endpoints
 */

import apiClient from "./client";
import { Topic, TopicListResponse, PaginationParams } from "../types";

export const topicsAPI = {
  // List all topics
  list: async (params?: PaginationParams): Promise<Topic[]> => {
    const response = await apiClient.get("/knowledge/topics/", { params });
    // Handle paginated response
    return Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
  },

  // Get topic by ID
  getById: async (id: string): Promise<Topic> => {
    const response = await apiClient.get(`/knowledge/topics/${id}/`);
    return response.data;
  },

  // List topics by module
  listByModule: async (
    moduleId: string,
    params?: PaginationParams,
  ): Promise<Topic[]> => {
    const response = await apiClient.get("/knowledge/topics/", {
      params: { ...params, module_id: moduleId },
    });
    // Handle paginated response
    return Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
  },

  // List topics by subject
  listBySubject: async (
    subjectId: string,
    params?: PaginationParams,
  ): Promise<Topic[]> => {
    const response = await apiClient.get("/knowledge/topics/", {
      params: { ...params, subject_id: subjectId },
    });
    // Handle paginated response
    return Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
  },
};
