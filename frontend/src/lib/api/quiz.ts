/**
 * Quiz API Client
 * 
 * All API calls for Assessment Engine.
 * Uses existing apiClient from @/lib/api/client
 */

import apiClient from './client';
import {
  Quiz,
  QuizAttempt,
  QuizGenerateRequest,
  QuizSubmitRequest,
  TopicMastery,
} from '../types';

export const quizAPI = {
  /**
   * Generate a new quiz
   */
  generateQuiz: async (data: QuizGenerateRequest): Promise<Quiz> => {
    const response = await apiClient.post('/assessment/generate/', data);
    return response.data;
  },

  /**
   * List available quizzes with filters
   */
  listQuizzes: async (params?: {
    topic_id?: string;
    difficulty?: 'easy' | 'medium' | 'hard';
    include_ca?: boolean;
  }): Promise<Quiz[]> => {
    const response = await apiClient.get('/assessment/quizzes/', { params });
    return response.data;
  },

  /**
   * Get quiz details (without correct answers)
   */
  getQuiz: async (quizId: string): Promise<Quiz> => {
    const response = await apiClient.get(`/assessment/quizzes/${quizId}/`);
    return response.data;
  },

  /**
   * Start a new quiz attempt
   */
  startQuiz: async (quizId: string): Promise<QuizAttempt> => {
    const response = await apiClient.post(`/assessment/quizzes/${quizId}/start/`);
    return response.data;
  },

  /**
   * Submit quiz with answers
   */
  submitQuiz: async (data: QuizSubmitRequest): Promise<QuizAttempt> => {
    const response = await apiClient.post('/assessment/submit/', data);
    return response.data;
  },

  /**
   * Get attempt result
   */
  getAttemptResult: async (attemptId: string): Promise<QuizAttempt> => {
    const response = await apiClient.get(`/assessment/attempts/${attemptId}/`);
    return response.data;
  },

  /**
   * List user's quiz attempts
   */
  listMyAttempts: async (params?: {
    quiz_id?: string;
    status?: 'active' | 'submitted' | 'abandoned';
  }): Promise<QuizAttempt[]> => {
    const response = await apiClient.get('/assessment/my-attempts/', { params });
    return response.data;
  },

  /**
   * Get topic mastery scores
   */
  getTopicMastery: async (params?: {
    topic_id?: string;
  }): Promise<TopicMastery[]> => {
    const response = await apiClient.get('/assessment/mastery/', { params });
    return response.data;
  },
};
