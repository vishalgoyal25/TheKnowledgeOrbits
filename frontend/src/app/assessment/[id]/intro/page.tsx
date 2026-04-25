/**
 * Quiz Intro Page — Briefing Room
 *
 * Shows quiz metadata (title, question count, time limit) and instructions
 * before the user enters the exam hall. The actual attempt is created only
 * when the user lands on /assessment/[id] — NOT here.
 *
 * Navigation flow:
 *   Homepage widget  →  /assessment/[id]/intro  →  /assessment/[id]  (exam hall)
 *
 * localStorage key `quiz_visited_<quizId>` tracks whether this user has
 * attempted the quiz before (guest-friendly, no auth required).
 */

"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuiz } from "@/lib/hooks/use-quiz";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  ArrowRight,
  Clock,
  FileQuestion,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";

export default function QuizIntroPage() {
  const params = useParams();
  const router = useRouter();
  const quizId = params.id as string;

  const { data: quiz, isLoading } = useQuiz(quizId);
  const [hasAttempted, setHasAttempted] = useState(false);

  // Check localStorage for previous visit (guest-friendly)
  useEffect(() => {
    if (!quizId) return;
    try {
      const visited = localStorage.getItem(`quiz_visited_${quizId}`);
      if (visited) setHasAttempted(true);
    } catch {
      // localStorage unavailable (private browsing edge case) — silently ignore
    }
  }, [quizId]);

  const handleStart = () => {
    try {
      localStorage.setItem(`quiz_visited_${quizId}`, "true");
    } catch {
      // Ignore localStorage errors
    }
    router.push(`/assessment/${quizId}`);
  };

  // ── Loading skeleton ─────────────────────────────────────────────────────
  if (isLoading || !quiz) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-violet-50 via-white to-slate-50 flex flex-col">
        <div className="container mx-auto px-4 py-10 max-w-2xl">
          <Skeleton className="h-8 w-40 mb-8" />
          <div className="bg-white rounded-3xl border border-slate-200 overflow-hidden shadow-lg">
            <div className="bg-violet-100 px-8 py-7">
              <Skeleton className="h-5 w-24 mb-3" />
              <Skeleton className="h-8 w-3/4" />
            </div>
            <div className="flex border-b border-slate-100">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex-1 px-6 py-4 text-center">
                  <Skeleton className="h-7 w-10 mx-auto mb-1" />
                  <Skeleton className="h-3 w-16 mx-auto" />
                </div>
              ))}
            </div>
            <div className="px-8 py-7 space-y-3">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <Skeleton key={i} className="h-4 w-full" />
              ))}
              <Skeleton className="h-12 w-full mt-6 rounded-lg" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  const timeMins = quiz.time_limit ? Math.round(quiz.time_limit / 60) : null;

  const instructions = [
    "Each question has exactly one correct answer.",
    "Based on today's current affairs — test real-world UPSC knowledge.",
    "No negative marking — attempt every question.",
    "Once submitted, view detailed explanations with source links.",
    timeMins
      ? `You have ${timeMins} minutes. The quiz auto-submits when time runs out.`
      : "No time limit on this quiz — take your time.",
    "You can re-attempt this quiz any number of times.",
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-violet-50 via-white to-slate-50 flex flex-col">
      <div className="container mx-auto px-4 py-10 max-w-2xl">
        {/* Back link */}
        <Link href="/">
          <Button variant="ghost" className="mb-6 gap-2 text-slate-600 hover:text-slate-900">
            <ArrowLeft className="h-4 w-4" />
            Back to Home
          </Button>
        </Link>

        {/* Briefing card */}
        <div className="bg-white rounded-3xl border border-slate-200 shadow-xl shadow-slate-100/60 overflow-hidden">
          {/* Header band */}
          <div className="bg-gradient-to-r from-violet-600 to-purple-600 px-8 py-7 text-white">
            <Badge className="bg-white/20 text-white border-white/30 mb-3 text-xs font-semibold">
              Daily Public Quiz
            </Badge>
            <h1 className="text-xl sm:text-2xl font-bold leading-tight">
              {quiz.title}
            </h1>
          </div>

          {/* Stats row */}
          <div className="flex divide-x divide-slate-100 border-b border-slate-100">
            <div className="flex-1 px-6 py-4 text-center">
              <div className="flex items-center justify-center gap-1.5 text-violet-600 mb-1">
                <FileQuestion className="h-4 w-4" />
                <span className="text-xl font-bold">{quiz.question_count}</span>
              </div>
              <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide">
                Questions
              </p>
            </div>

            {timeMins && (
              <div className="flex-1 px-6 py-4 text-center">
                <div className="flex items-center justify-center gap-1.5 text-violet-600 mb-1">
                  <Clock className="h-4 w-4" />
                  <span className="text-xl font-bold">{timeMins}</span>
                </div>
                <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide">
                  Minutes
                </p>
              </div>
            )}

            <div className="flex-1 px-6 py-4 text-center">
              <div className="flex items-center justify-center gap-1.5 text-violet-600 mb-1">
                <RotateCcw className="h-4 w-4" />
                <span className="text-xl font-bold">∞</span>
              </div>
              <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide">
                Re-attempts
              </p>
            </div>
          </div>

          {/* Instructions */}
          <div className="px-8 py-7">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">
              Instructions
            </h2>

            <ul className="space-y-3">
              {instructions.map((inst) => (
                <li
                  key={inst}
                  className="flex items-start gap-3 text-sm text-slate-600 leading-relaxed"
                >
                  <ShieldCheck className="h-4 w-4 text-violet-400 mt-0.5 shrink-0" />
                  {inst}
                </li>
              ))}
            </ul>

            {/* Previous attempt notice */}
            {hasAttempted && (
              <div className="mt-5 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
                <p className="text-sm text-amber-700 font-medium">
                  You&apos;ve attempted this quiz before. Starting again will
                  create a fresh attempt with a new score.
                </p>
              </div>
            )}

            {/* CTA */}
            <Button
              onClick={handleStart}
              size="lg"
              className="w-full mt-7 h-12 text-base bg-violet-600 hover:bg-violet-700 shadow-lg shadow-violet-900/10 gap-2 group"
            >
              {hasAttempted ? "Re-attempt Quiz" : "Start Quiz"}
              <ArrowRight className="h-5 w-5 group-hover:translate-x-0.5 transition-transform" />
            </Button>

            <p className="text-center text-xs text-slate-400 mt-3">
              No login required · Results visible immediately after submission
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
