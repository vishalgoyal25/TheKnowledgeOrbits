import apiClient from './client';
import { Article } from '@/types/notebook';

export const notebookAPI = {
  // Get user's private articles (My Notebook)
  getMyArticles: async (): Promise<Article[]> => {
    const response = await apiClient.get('/articles/my-notebook/');
    return response.data;
  },

  // Delete article
  deleteArticle: async (articleId: string): Promise<void> => {
    await apiClient.delete(`/articles/${articleId}/`);
  },

  // Generate new article
  generateArticle: async (data: { topic_id: string; include_ca: boolean }): Promise<Article> => {
    const response = await apiClient.post('/articles/generate/', data);
    return response.data;
  },
};
