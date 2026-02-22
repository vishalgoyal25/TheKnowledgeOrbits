/**
 * Quiz React Query Hooks
 *
 * Custom hooks for quiz operations with caching and optimistic updates.
 */

"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { quizAPI } from "../api/quiz";
import { QuizGenerateRequest, QuizSubmitRequest } from "../types";
import { toast } from "@/hooks/use-toast";

// ===== Query Keys =====

export const quizKeys = {
  all: ["quizzes"] as const,
  lists: () => [...quizKeys.all, "list"] as const,
  list: (filters: Record<string, any>) =>
    [...quizKeys.lists(), filters] as const,
  details: () => [...quizKeys.all, "detail"] as const,
  detail: (id: string) => [...quizKeys.details(), id] as const,
  attempts: () => [...quizKeys.all, "attempts"] as const,
  attempt: (id: string) => [...quizKeys.attempts(), id] as const,
  myAttempts: (filters: Record<string, any>) =>
    [...quizKeys.attempts(), "my", filters] as const,
  mastery: () => ["mastery"] as const,
};

// ===== List Quizzes =====

export function useQuizzes(params?: {
  topic_id?: string;
  difficulty?: "easy" | "medium" | "hard";
  include_ca?: boolean;
}) {
  return useQuery({
    queryKey: quizKeys.list(params || {}),
    queryFn: () => quizAPI.listQuizzes(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// ===== Get Quiz Detail =====

export function useQuiz(quizId: string | null) {
  return useQuery({
    queryKey: quizKeys.detail(quizId!),
    queryFn: () => quizAPI.getQuiz(quizId!),
    enabled: !!quizId,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// ===== Generate Quiz =====

export function useGenerateQuiz() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: QuizGenerateRequest) => quizAPI.generateQuiz(data),
    onSuccess: (newQuiz) => {
      // Invalidate quiz lists
      queryClient.invalidateQueries({ queryKey: quizKeys.lists() });

      toast({
        title: "Quiz generated successfully!",
        description: `${newQuiz.question_count} questions created`,
      });
    },
    onError: (error: any) => {
      toast({
        title: "Failed to generate quiz",
        description: error.response?.data?.message || "Please try again",
        variant: "destructive",
      });
    },
  });
}

// ===== Start Quiz =====

export function useStartQuiz() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (quizId: string) => quizAPI.startQuiz(quizId),
    onSuccess: (attempt) => {
      // Cache the attempt
      queryClient.setQueryData(quizKeys.attempt(attempt.id), attempt);

      toast({
        title: "Quiz started!",
        description: "Good luck!",
      });
    },
    onError: (error: any) => {
      const message = error.response?.data?.message || "Failed to start quiz";
      toast({
        title: "Cannot start quiz",
        description: message,
        variant: "destructive",
      });
    },
  });
}

// ===== Submit Quiz =====

export function useSubmitQuiz() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: QuizSubmitRequest) => quizAPI.submitQuiz(data),
    onSuccess: (result) => {
      // Update attempt cache
      queryClient.setQueryData(quizKeys.attempt(result.id), result);

      // Invalidate attempts list
      queryClient.invalidateQueries({ queryKey: quizKeys.attempts() });

      // Invalidate mastery (will be updated)
      queryClient.invalidateQueries({ queryKey: quizKeys.mastery() });

      toast({
        title: "Quiz submitted!",
        description: `You scored ${result.score?.toFixed(1)}%`,
      });
    },
    onError: (error: any) => {
      toast({
        title: "Failed to submit quiz",
        description: error.response?.data?.message || "Please try again",
        variant: "destructive",
      });
    },
  });
}

// ===== Get Attempt Result =====

export function useAttemptResult(attemptId: string | null) {
  return useQuery({
    queryKey: quizKeys.attempt(attemptId!),
    queryFn: () => quizAPI.getAttemptResult(attemptId!),
    enabled: !!attemptId,
    staleTime: Infinity, // Results don't change
  });
}

// ===== List My Attempts =====

// ===== List My Attempts =====

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

export function useTopicMastery(params?: { topic_id?: string }) {
  return useQuery({
    queryKey: [...quizKeys.mastery(), params || {}],
    queryFn: () => quizAPI.getTopicMastery(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
