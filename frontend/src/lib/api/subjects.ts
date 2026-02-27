/**
 * Subjects, Modules API endpoints
 */

import apiClient from "./client";

export interface Subject {
  id: string;
  name: string;
  description: string;
  program: string;
  order_index: number;
  is_active: boolean;
}

export interface Module {
  id: string;
  name: string;
  description: string;
  subject: string;
  order_index: number;
  is_active: boolean;
}

export const subjectsAPI = {
  // List subjects
  list: async () => {
    const response = await apiClient.get("/knowledge/subjects/");
    // Handle paginated response
    return Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
  },

  // Get subject by ID
  getById: async (id: string) => {
    const response = await apiClient.get(`/knowledge/subjects/${id}/`);
    return response.data;
  },

  // List modules by subject
  getModulesBySubject: async (subjectId: string) => {
    const response = await apiClient.get("/knowledge/modules/", {
      params: { subject_id: subjectId },
    });
    return response.data;
  },
};
