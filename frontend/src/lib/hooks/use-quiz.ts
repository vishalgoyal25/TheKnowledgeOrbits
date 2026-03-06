/**
 * Quiz React Query Hooks
 *
 * Custom hooks for quiz operations with caching and optimistic updates.
 */

"use client";

import { toast } from "@/hooks/use-toast";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { quizAPI } from "../api/quiz";
import {
  ApiError,
  Quiz,
  QuizAttempt,
  QuizGenerateRequest,
  QuizSubmitRequest,
} from "../types";

// ===== Query Keys =====

/**
 * Centrally managed query keys for the quiz engine.
 * Ensures consistent cache invalidation across the app.
 */
export const quizKeys = {
  all: ["quizzes"] as const,
  lists: () => [...quizKeys.all, "list"] as const,
  list: (filters: Record<string, string | number | boolean | undefined>) =>
    [...quizKeys.lists(), filters] as const,
  details: () => [...quizKeys.all, "detail"] as const,
  detail: (id: string) => [...quizKeys.details(), id] as const,
  attempts: () => [...quizKeys.all, "attempts"] as const,
  attempt: (id: string) => [...quizKeys.attempts(), id] as const,
  myAttempts: (
    filters: Record<string, string | number | boolean | undefined>,
  ) => [...quizKeys.attempts(), "my", filters] as const,
  mastery: () => ["mastery"] as const,
};

// ===== List Quizzes =====

/**
 * Hook to fetch a list of available quizzes with optional filtering.
 *
 * @param params - Filter parameters (topic, difficulty, current affairs)
 */
export function useQuizzes(params?: {
  topic_id?: string;
  difficulty?: "easy" | "medium" | "hard";
  include_ca?: boolean;
}) {
  return useQuery({
    queryKey: quizKeys.list(params || {}),
    queryFn: () => quizAPI.listQuizzes(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000,
  });
}

// ===== Get Quiz Detail =====

/**
 * Hook to fetch complete details of a specific quiz.
 *
 * @param quizId - The UUID of the quiz to fetch
 */
export function useQuiz(quizId: string | null) {
  return useQuery({
    queryKey: quizKeys.detail(quizId!),
    queryFn: () => quizAPI.getQuiz(quizId!),
    enabled: !!quizId,
    staleTime: 10 * 60 * 1000, // 10 minutes
    gcTime: 60 * 60 * 1000,
  });
}

/**
 * Hook to trigger the AI generation of a new quiz based on parameters.
 *
 * Handles submission to the backend engine and automatic cache invalidation
 * to ensure new quizzes appear in the list immediately.
 */
export function useGenerateQuiz() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: QuizGenerateRequest) => quizAPI.generateQuiz(data),
    onSuccess: (newQuiz: Quiz) => {
      // Invalidate quiz lists to show the new quiz
      queryClient.invalidateQueries({ queryKey: quizKeys.lists() });

      toast({
        title: "Quiz generated successfully!",
        description: `${newQuiz.question_count} questions created`,
      });
    },
    onError: (error: AxiosError<ApiError>) => {
      toast({
        title: "Failed to generate quiz",
        description:
          error.response?.data?.message ||
          error.response?.data?.error ||
          "Please try again",
        variant: "destructive",
      });
    },
  });
}

// ===== Start Quiz =====

/**
 * Hook to create a new quiz attempt (starts the timer on backend).
 */
export function useStartQuiz() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (quizId: string) => quizAPI.startQuiz(quizId),
    onSuccess: (attempt: QuizAttempt) => {
      // Cache the attempt data immediately
      queryClient.setQueryData(quizKeys.attempt(attempt.id), attempt);

      toast({
        title: "Quiz started!",
        description: "Good luck!",
      });
    },
    onError: (error: AxiosError<ApiError>) => {
      const message =
        error.response?.data?.message ||
        error.response?.data?.error ||
        "Failed to start quiz";
      toast({
        title: "Cannot start quiz",
        description: message,
        variant: "destructive",
      });
    },
  });
}

// ===== Submit Quiz =====

/**
 * Hook to submit answers for a quiz attempt and calculate results.
 */
export function useSubmitQuiz() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: QuizSubmitRequest) => quizAPI.submitQuiz(data),
    onSuccess: (result: QuizAttempt) => {
      // Update specific attempt cache with final results
      queryClient.setQueryData(quizKeys.attempt(result.id), result);

      // Invalidate all related lists to ensure UI consistency
      queryClient.invalidateQueries({ queryKey: quizKeys.attempts() });
      queryClient.invalidateQueries({ queryKey: quizKeys.mastery() });

      // Invalidate dashboard cache (stats changed after quiz)
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });

      toast({
        title: "Quiz submitted!",
        description: `You scored ${result.score?.toFixed(1) ?? 0}%`,
      });
    },
    onError: (error: AxiosError<ApiError>) => {
      toast({
        title: "Failed to submit quiz",
        description:
          error.response?.data?.message ||
          error.response?.data?.error ||
          "Please try again",
        variant: "destructive",
      });
    },
  });
}

// ===== Get Attempt Result =====

/**
 * Hook to fetch the results of a completed quiz attempt.
 */
export function useAttemptResult(attemptId: string | null) {
  return useQuery({
    queryKey: quizKeys.attempt(attemptId!),
    queryFn: () => quizAPI.getAttemptResult(attemptId!),
    enabled: !!attemptId,
    staleTime: Infinity, // Completion results are immutable
  });
}

// ===== List My Attempts =====

/**
 * Hook to list all quiz attempts for the current user.
 */
export function useMyAttempts(
  params?: {
    quiz_id?: string;
    status?: "active" | "submitted" | "abandoned";
  },
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: quizKeys.myAttempts(params || {}),
    queryFn: () => quizAPI.listMyAttempts(params),
    staleTime: 2 * 60 * 1000, // 2 minutes
    enabled: options?.enabled,
  });
}

// ===== Get Topic Mastery =====

/**
 * Hook to get the user's mastery level for a specific topic or all topics.
 */
export function useTopicMastery(params?: { topic_id?: string }) {
  return useQuery({
    queryKey: [...quizKeys.mastery(), params || {}],
    queryFn: () => quizAPI.getTopicMastery(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
