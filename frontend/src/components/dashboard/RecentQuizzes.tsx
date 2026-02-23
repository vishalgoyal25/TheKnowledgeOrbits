"use client";

import { useMyAttempts } from "@/lib/hooks/use-quiz";
import Link from "next/link";
import { History, ArrowRight } from "lucide-react";
import AttemptCard from "@/components/quiz/attempt-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { QuizAttempt } from "@/lib/types";

interface RecentQuizzesProps {
  isGuest?: boolean;
}

/**
 * RecentQuizzes - Dashboard widget to display user's recent quiz attempts.
 * Supports a guest mode showing static mock data.
 */
export default function RecentQuizzes({ isGuest = false }: RecentQuizzesProps) {
  /** Static mock data for guests or landing page demonstration. */
  const MOCK_ATTEMPTS: QuizAttempt[] = [
    {
      id: "mock-1",
      quiz: {
        id: "mock-q1",
        title: "Indian Polity: Preamble",
        topic: { name: "Polity" } as unknown as any, // Using unknown as bridge
        question_count: 10,
      } as unknown as any,
      status: "submitted",
      score: 80,
      accuracy: 80,
      correct_count: 8,
      wrong_count: 2,
      unanswered_count: 0,
      started_at: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
      submitted_at: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
      time_spent: 600,
    } as unknown as QuizAttempt,
    {
      id: "mock-2",
      quiz: {
        id: "mock-q2",
        title: "Modern History: Gandhian Era",
        topic: { name: "History" } as unknown as any,
        question_count: 15,
      } as unknown as any,
      status: "active",
      score: null,
      accuracy: 0,
      correct_count: 0,
      wrong_count: 0,
      unanswered_count: 15,
      started_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      submitted_at: null,
      time_spent: 120,
    } as unknown as QuizAttempt,
  ];
  // Only fetch if not guest
  const { data: attempts, isLoading } = useMyAttempts(undefined, {
    enabled: !isGuest,
  });

  // If guest, use MOCK_ATTEMPTS. If loading (and not guest), wait. If not loading, use fetched data.
  const displayAttempts = isGuest ? MOCK_ATTEMPTS : attempts?.slice(0, 2) || [];
  const showLoading = !isGuest && isLoading;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
          <History className="h-5 w-5 text-blue-600" />
          Recent Quizzes
        </h2>
        <Link href="/assessment/history">
          <Button
            variant="ghost"
            size="sm"
            className="gap-1 text-blue-600 hover:text-blue-700"
          >
            View History <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>

      {showLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-40 w-full rounded-xl" />
          <Skeleton className="h-40 w-full rounded-xl" />
        </div>
      ) : displayAttempts.length === 0 ? (
        <div className="bg-white p-8 rounded-xl border border-dashed border-gray-200 text-center shadow-sm">
          <p className="text-gray-500 text-sm mb-3">No quizzes attempted yet</p>
          <Link href="/assessment/generate">
            <Button size="sm">Start a Quiz</Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {displayAttempts.map((attempt) => (
            <AttemptCard key={attempt.id} attempt={attempt} />
          ))}
        </div>
      )}
    </div>
  );
}
