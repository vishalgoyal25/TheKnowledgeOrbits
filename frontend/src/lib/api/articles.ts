/**
 * Article API endpoints
 */

import apiClient from './client';
import {
  Article,
  ArticleListResponse,
  ArticleSourcesResponse,
  ArticleGenerationRequest,
  ArticleGenerationResponse,
  ArticleFilterParams,
} from '../types';

export const articlesAPI = {
  // List articles
  list: async (params?: ArticleFilterParams): Promise<ArticleListResponse> => {
    const response = await apiClient.get('/articles/', { params });
    return response.data;
  },
  
  // Get article by ID
  getById: async (id: string): Promise<Article> => {
    const response = await apiClient.get(`/articles/${id}/`);
    return response.data;
  },
  
  // Get article by slug
  getBySlug: async (slug: string): Promise<Article> => {
    const response = await apiClient.get(`/articles/`, {
      params: { slug },
    });
    return response.data.results[0];
  },
  
  // Get article sources
  getSources: async (id: string): Promise<ArticleSourcesResponse> => {
    const response = await apiClient.get(`/articles/${id}/sources/`);
    return response.data;
  },
  
  // Generate article
  generate: async (data: ArticleGenerationRequest): Promise<ArticleGenerationResponse> => {
    const response = await apiClient.post('/articles/generate/', data);
    return response.data;
  },
  
  // List articles by topic
  listByTopic: async (topicId: string, params?: ArticleFilterParams): Promise<ArticleListResponse> => {
    const response = await apiClient.get('/articles/', {
      params: { ...params, topic_id: topicId },
    });
    return response.data;
  },
};
