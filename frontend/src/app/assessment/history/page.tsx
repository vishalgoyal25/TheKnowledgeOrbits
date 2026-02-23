"use client";

import { useMyAttempts } from "@/lib/hooks/use-quiz";
import AttemptCard from "@/components/quiz/attempt-card";
import { Skeleton } from "@/components/ui/skeleton";
import { History, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

/**
 * QuizHistoryPage - A dedicated dashboard for tracking user assessment performance.
 * 
 * Lists all previous quiz attempts in reverse chronological order, allowing the user
 * to review scores, analyze mistakes, and jump back into unfinished sessions.
 * Provides a clean empty state to encourage the user to generate their first quiz.
 */
export default function QuizHistoryPage() {
  const { data: attempts, isLoading } = useMyAttempts();

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Skeleton className="h-10 w-32" />
        </div>
        <Skeleton className="h-12 w-64 mb-6" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-48 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <Link href="/assessment">
            <Button
              variant="ghost"
              className="gap-2 pl-0 text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Quizzes
            </Button>
          </Link>
        </div>

        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-blue-100 rounded-lg">
            <History className="h-6 w-6 text-blue-600" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Quiz History</h1>
        </div>
        <p className="text-muted-foreground ml-12">
          Review your past quiz attempts and track your progress over time.
        </p>
      </div>

      {/* Grid */}
      {!attempts || attempts.length === 0 ? (
        <div className="text-center py-20 bg-muted/30 rounded-lg border border-dashed">
          <div className="bg-muted p-4 rounded-full w-fit mx-auto mb-4">
            <History className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-xl font-semibold mb-2">No attempts yet</h3>
          <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
            You haven't taken any quizzes yet. Start generating quizzes to track
            your performance.
          </p>
          <Link href="/assessment/generate">
            <Button className="gap-2">Generate Your First Quiz</Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {attempts.map((attempt) => (
            <AttemptCard key={attempt.id} attempt={attempt} />
          ))}
        </div>
      )}
    </div>
  );
}
