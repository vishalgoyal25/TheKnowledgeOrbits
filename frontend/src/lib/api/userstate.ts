/**
 * User State API - Handles user-specific progress, streaks, and preferences
 */

import apiClient from "./client";

export interface UserProgress {
  total_points: number;
  level: number;
  current_streak: number;
  longest_streak: number;
  last_active: string;
  syllabus_completion: number;
}

export interface UserPreferences {
  daily_goal: number;
  notification_enabled: boolean;
  theme: "light" | "dark" | "system";
}

export const userStateAPI = {
  // Get overall user progress
  getProgress: async (): Promise<UserProgress> => {
    const response = await apiClient.get("/users/me/progress/");
    return response.data;
  },

  // Update user active status (heartbeat)
  updateActivity: async (): Promise<{ streak: number }> => {
    const response = await apiClient.post("/users/me/activity/");
    return response.data;
  },

  // Get user preferences
  getPreferences: async (): Promise<UserPreferences> => {
    const response = await apiClient.get("/users/me/preferences/");
    return response.data;
  },

  // Update user preferences
  updatePreferences: async (
    prefs: Partial<UserPreferences>,
  ): Promise<UserPreferences> => {
    const response = await apiClient.patch("/users/me/preferences/", prefs);
    return response.data;
  },

  // Get syllabus coverage details
  getSyllabusCoverage: async (): Promise<Record<string, unknown>> => {
    const response = await apiClient.get("/users/me/syllabus-coverage/");
    return response.data;
  },
};
