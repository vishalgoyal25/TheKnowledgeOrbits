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
    return Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
  },

  // Get module by ID
  getModuleById: async (id: string) => {
    const response = await apiClient.get(`/knowledge/modules/${id}/`);
    return response.data;
  },

  // Get complete master hierarchy for Navigation.
  // Backend returns program-wrapped: [{id, name, subjects: [...]}].
  // We flatten to HierarchySubject[] to match the server-side ISR format.
  getHierarchy: async () => {
    const response = await apiClient.get("/knowledge/hierarchy/");
    const data = response.data;
    if (Array.isArray(data) && data.length > 0 && data[0]?.subjects) {
      return data.flatMap(
        (program: { subjects?: unknown[] }) => program.subjects || [],
      );
    }
    return Array.isArray(data) ? data : [];
  },
};
