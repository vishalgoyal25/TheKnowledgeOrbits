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

const MOCK_ATTEMPTS: any[] = [
  {
    id: "mock-1",
    quiz: {
      id: "mock-q1",
      title: "Indian Polity: Preamble",
      topic: { name: "Polity" },
      question_count: 10,
    },
    status: "submitted",
    score: 80,
    started_at: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: "mock-2",
    quiz: {
      id: "mock-q2",
      title: "Modern History: Gandhian Era",
      topic: { name: "History" },
      question_count: 15,
    },
    status: "active",
    score: null,
    started_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
];

export default function RecentQuizzes({ isGuest = false }: RecentQuizzesProps) {
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
