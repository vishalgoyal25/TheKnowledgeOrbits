/**
 * Current Affairs API endpoints
 */

import apiClient from './client';
import {
  CASource,
  CAArticle,
  CAChunk,
  CATopicLink,
  CAArticleListResponse,
  CAChunkListResponse,
  CASourceListResponse,
  CATopicLinkListResponse,
  PaginationParams,
} from '../types';

export interface CAArticleFilterParams extends PaginationParams {
  source_id?: string;
  date_from?: string;
  date_to?: string;
  status?: string;
  ordering?: string;
}

export interface CAChunkFilterParams extends PaginationParams {
  topic_id?: string;
  date_from?: string;
  date_to?: string;
  include_expired?: boolean;
  ordering?: string;
}

export const currentAffairsAPI = {
  // Sources
  listSources: async (): Promise<CASourceListResponse> => {
    const response = await apiClient.get('/ca/sources/');
    return response.data;
  },
  
  getSource: async (id: string): Promise<CASource> => {
    const response = await apiClient.get(`/ca/sources/${id}/`);
    return response.data;
  },
  
  // Articles
  listArticles: async (params?: CAArticleFilterParams): Promise<CAArticleListResponse> => {
    const response = await apiClient.get('/ca/articles/', { params });
    return response.data;
  },
  
  getArticle: async (id: string): Promise<CAArticle> => {
    const response = await apiClient.get(`/ca/articles/${id}/`);
    return response.data;
  },
  
  // Chunks
  listChunks: async (params?: CAChunkFilterParams): Promise<CAChunkListResponse> => {
    const response = await apiClient.get('/ca/chunks/', { params });
    return response.data;
  },
  
  getChunk: async (id: string): Promise<CAChunk> => {
    const response = await apiClient.get(`/ca/chunks/${id}/`);
    return response.data;
  },
  
  getRecentChunks: async (): Promise<CAChunk[]> => {
    const response = await apiClient.get('/ca/chunks/recent/');
    return response.data;
  },
  
  // Topic Links
  listTopicLinks: async (params?: { topic_id?: string; link_method?: string }): Promise<CATopicLinkListResponse> => {
    const response = await apiClient.get('/ca/links/', { params });
    return response.data;
  },
  
  // Get CA chunks for a specific topic
  getChunksForTopic: async (topicId: string, days: number = 30): Promise<CAChunk[]> => {
    const dateFrom = new Date();
    dateFrom.setDate(dateFrom.getDate() - days);
    
    const response = await apiClient.get('/ca/chunks/', {
      params: {
        topic_id: topicId,
        date_from: dateFrom.toISOString(),
        ordering: '-published_at',
      },
    });
    return response.data.results;
  },
};
