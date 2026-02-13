/**
 * Search API endpoints
 */

import apiClient from './client';

export interface SearchParams {
  q: string;
  type?: 'articles' | 'topics' | 'all';
  limit?: number;
}

export interface SearchResult {
  type: 'article' | 'topic';
  id: string;
  title: string;
  snippet: string;
  relevance: number;
  metadata: Record<string, any>;
}

export const searchAPI = {
  // Search across articles and topics
  search: async (params: SearchParams) => {
    const { q, type = 'all', limit = 20 } = params;
    
    // For now, search articles and topics separately
    // In production, implement unified search endpoint
    const results: SearchResult[] = [];
    
    if (type === 'all' || type === 'articles') {
      const articlesResponse = await apiClient.get('/articles/', {
        params: { search: q, limit },
      });
      
      articlesResponse.data.results?.forEach((article: any) => {
        results.push({
          type: 'article',
          id: article.id,
          title: article.title,
          snippet: article.summary || article.content.substring(0, 150),
          relevance: 1.0,
          metadata: {
            topic: article.topic?.name,
            word_count: article.word_count,
            created_at: article.created_at,
          },
        });
      });
    }
    
    if (type === 'all' || type === 'topics') {
      const topicsResponse = await apiClient.get('/knowledge/topics/', {
        params: { search: q, limit },
      });
      
      topicsResponse.data.results?.forEach((topic: any) => {
        results.push({
          type: 'topic',
          id: topic.id,
          title: topic.name,
          snippet: topic.description || '',
          relevance: 0.8,
          metadata: {
            subject: topic.subject?.name,
            difficulty: topic.difficulty_level,
          },
        });
      });
    }
    
    // Sort by relevance
    results.sort((a, b) => b.relevance - a.relevance);
    
    return results;
  },
};
