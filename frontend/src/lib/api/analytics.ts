import apiClient from './client';
import { DashboardOverview, WeeklyStats } from '@/types/dashboard';

export const analyticsAPI = {
  getDashboard: async (): Promise<DashboardOverview> => {
    const response = await apiClient.get('/analytics/dashboard/');
    return response.data;
  },

  getWeeklyStats: async (): Promise<WeeklyStats> => {
    const response = await apiClient.get('/analytics/weekly-stats/');
    return response.data;
  },

  getMonthlyStats: async () => {
    const response = await apiClient.get('/analytics/monthly-stats/');
    return response.data;
  },

  generateInsights: async () => {
    const response = await apiClient.post('/analytics/generate-insights/');
    return response.data;
  },
};
