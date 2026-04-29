/**
 * analytics.ts — Dashboard and insights API calls.
 * All endpoints map to engines/analytics/ backend.
 *
 *   GET  /api/v1/analytics/dashboard/         — full dashboard overview
 *   GET  /api/v1/analytics/weekly-stats/      — 7-day activity breakdown
 *   GET  /api/v1/analytics/monthly-stats/     — 30-day activity breakdown
 *   GET  /api/v1/analytics/insights/          — fetch active insights
 *   POST /api/v1/analytics/generate-insights/ — trigger insight generation
 */

import apiClient from "./client";
import type {
  DashboardOverview,
  WeeklyStats,
  Insight,
} from "@/types/dashboard";

export const analyticsAPI = {
  getDashboard: async (): Promise<DashboardOverview> => {
    const response = await apiClient.get("/analytics/dashboard/");
    return response.data;
  },

  getWeeklyStats: async (): Promise<WeeklyStats> => {
    const response = await apiClient.get("/analytics/weekly-stats/");
    return response.data;
  },

  getMonthlyStats: async (): Promise<WeeklyStats> => {
    const response = await apiClient.get("/analytics/monthly-stats/");
    return response.data;
  },

  getInsights: async (): Promise<Insight[]> => {
    const response = await apiClient.get("/analytics/insights/");
    return response.data;
  },

  generateInsights: async (): Promise<Insight[]> => {
    const response = await apiClient.post("/analytics/generate-insights/");
    return response.data;
  },
};
