import apiClient from "./client";
import { Bookmark } from "@/types/notebook";

export const bookmarksAPI = {
  // Get all bookmarks
  getBookmarks: async (
    contentType?: "article" | "quiz",
  ): Promise<Bookmark[]> => {
    const params = contentType ? { content_type: contentType } : {};
    const response = await apiClient.get("/userstate/bookmarks/", { params });
    // Handle paginated response
    const results = Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
    return results;
  },

  // Add bookmark
  addBookmark: async (data: {
    content_type: string;
    content_id: string;
    notes?: string;
  }): Promise<Bookmark> => {
    const response = await apiClient.post("/userstate/bookmarks/add/", data);
    return response.data;
  },

  // Remove bookmark
  removeBookmark: async (bookmarkId: string): Promise<void> => {
    await apiClient.delete(`/userstate/bookmarks/${bookmarkId}/`);
  },

  // Update notes (custom endpoint - may need backend update)
  updateNotes: async (bookmarkId: string, notes: string): Promise<Bookmark> => {
    const response = await apiClient.patch(
      `/userstate/bookmarks/${bookmarkId}/notes/`,
      { notes },
    );
    return response.data;
  },
};
