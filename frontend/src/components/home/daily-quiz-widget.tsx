/**
 * DailyQuizWidget — Homepage widget for the Daily Public Quiz.
 *
 * Mirrors the DailyCaTeaserWidget pattern:
 *   - ISR-preloaded today quiz passed as `initialTodayQuiz` prop
 *   - Date-tab navigation (Today + last 6 days) fetches via `getDailyQuizByDate`
 *   - Violet colour scheme to visually differentiate from the green CA section
 *
 * CTA links to /assessment/{quiz.id}/intro (briefing room) instead of
 * directly to the exam hall — giving users context before the clock starts.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getDailyPublicQuiz, getDailyQuizByDate } from "@/lib/api/quiz";
import type { Quiz } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowRight, Clock, FileQuestion, Zap } from "lucide-react";

// ── Date helpers ──────────────────────────────────────────────────────────────

function toISODate(d: Date): string {
  return d.toISOString().split("T")[0];
}

function todayISO(): string {
  return toISODate(new Date());
}

/** Returns last N days as ISO strings, newest first (index 0 = today). */
function lastNDays(n: number): string[] {
  return Array.from({ length: n }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - i);
    return toISODate(d);
  });
}

function chipLabel(iso: string, todayStr: string): string {
  if (iso === todayStr) return "Today";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

// ── Sub-components ────────────────────────────────────────────────────────────

function QuizCardSkeleton() {
  return (
    <div className="bg-white rounded-2xl border border-violet-100 p-6 shadow-sm">
      <div className="flex items-start justify-between mb-3">
        <Skeleton className="h-5 w-20 rounded-full" />
        <Skeleton className="h-4 w-10" />
      </div>
      <Skeleton className="h-6 w-4/5 mb-2" />
      <Skeleton className="h-4 w-3/5 mb-5" />
      <div className="flex gap-5 mb-5">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-20" />
      </div>
      <Skeleton className="h-10 w-full rounded-lg" />
    </div>
  );
}

function EmptyQuizCard({ dateLabel }: { dateLabel: string }) {
  return (
    <div className="bg-white rounded-2xl border-2 border-dashed border-violet-200 p-8 text-center">
      <div className="h-12 w-12 rounded-2xl bg-violet-50 flex items-center justify-center mx-auto mb-4">
        <FileQuestion className="h-6 w-6 text-violet-300" />
      </div>
      <p className="text-slate-700 font-semibold mb-1">
        No quiz for {dateLabel}
      </p>
      <p className="text-sm text-slate-400 max-w-xs mx-auto">
        Daily quizzes go live after Daily Current Affairs. Check back later.
      </p>
    </div>
  );
}

function ActiveQuizCard({ quiz }: { quiz: Quiz }) {
  const timeMins = quiz.time_limit ? Math.round(quiz.time_limit / 60) : null;

  return (
    <div className="bg-gradient-to-br from-violet-50 to-purple-50/60 rounded-2xl border border-violet-100 p-6 shadow-sm hover:shadow-md transition-shadow">
      {/* Badge row */}
      <div className="flex items-start justify-between mb-3">
        <Badge className="bg-violet-100 text-violet-700 border-violet-200 text-xs font-semibold gap-1">
          <Zap className="h-3 w-3" />
          Live Now
        </Badge>
        <span className="text-xs text-slate-400 font-medium">
          {quiz.question_count} Qs
        </span>
      </div>

      {/* Quiz title */}
      <h3 className="text-[15px] font-bold text-slate-800 leading-snug mb-4 line-clamp-2">
        {quiz.title}
      </h3>

      {/* Meta stats */}
      <div className="flex items-center gap-5 mb-5 text-sm text-slate-500">
        <span className="flex items-center gap-1.5">
          <FileQuestion className="h-3.5 w-3.5 text-violet-400" />
          {quiz.question_count} Questions
        </span>
        {timeMins && (
          <span className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-violet-400" />
            {timeMins} min
          </span>
        )}
      </div>

      {/* CTA → intro page, not exam hall directly */}
      <Link href={`/assessment/${quiz.id}/intro`}>
        <Button className="w-full bg-violet-600 hover:bg-violet-700 text-white gap-2 group/btn shadow-sm">
          Attempt Today&apos;s Quiz
          <ArrowRight className="h-4 w-4 group-hover/btn:translate-x-0.5 transition-transform" />
        </Button>
      </Link>
    </div>
  );
}

// ── Main Widget ───────────────────────────────────────────────────────────────

interface DailyQuizWidgetProps {
  /** Today's quiz pre-fetched via ISR in page.tsx. null = not yet generated. */
  initialTodayQuiz?: Quiz | null;
}

export function DailyQuizWidget({
  initialTodayQuiz = null,
}: DailyQuizWidgetProps) {
  const days = lastNDays(7);
  const todayStr = todayISO();

  const [activeDate, setActiveDate] = useState(todayStr);
  const [quiz, setQuiz] = useState<Quiz | null>(initialTodayQuiz);
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(initialTodayQuiz === null);

  /**
   * skipInitialFetch: true ONLY when today's quiz was successfully pre-loaded
   * from ISR props — avoids a redundant network call on first render.
   * When ISR returned null (Render cold start / quiz not yet generated at
   * revalidation time), we must NOT skip — the client-side fetch is the
   * only way to show the quiz without waiting for the next 5-min revalidation.
   */
  const skipInitialFetch = useRef(initialTodayQuiz !== null);

  const fetchQuiz = useCallback(
    async (date: string) => {
      setLoading(true);
      setNotFound(false);
      try {
        const data =
          date === todayStr
            ? await getDailyPublicQuiz()
            : await getDailyQuizByDate(date);

        if (data) {
          setQuiz(data);
          setNotFound(false);
        } else {
          setQuiz(null);
          setNotFound(true);
        }
      } finally {
        setLoading(false);
      }
    },
    [todayStr],
  );

  useEffect(() => {
    // Skip the very first render if today's data came from ISR
    if (skipInitialFetch.current) {
      skipInitialFetch.current = false;
      return;
    }
    fetchQuiz(activeDate);
  }, [activeDate, fetchQuiz]);

  const handleDateChange = (date: string) => {
    if (date === activeDate) return;
    setActiveDate(date);
  };

  const displayLabel = chipLabel(activeDate, todayStr);

  return (
    <section className="bg-gradient-to-b from-violet-50/70 to-white border-b border-violet-100/50 py-14">
      <div className="container mx-auto px-4 max-w-7xl">
        {/* Section header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 mb-8">
          <div>
            <div className="flex items-center gap-2.5 mb-1.5">
              <div className="h-7 w-7 rounded-lg bg-violet-100 flex items-center justify-center shrink-0">
                <FileQuestion className="h-4 w-4 text-violet-600" />
              </div>
              <h2 className="text-xl font-bold text-slate-900">
                Daily CA Quiz
              </h2>
              <Badge className="bg-violet-600 text-white border-transparent text-[10px] px-2 py-0.5 font-bold">
                PUBLIC
              </Badge>
            </div>
            <p className="text-sm text-slate-500 pl-9">
              10 UPSC-style questions · Published every morning · Free to
              attempt · No login needed
            </p>
          </div>

          <Link
            href="/assessment"
            className="text-violet-600 text-sm font-semibold flex items-center gap-1 hover:gap-2 transition-all pl-9 sm:pl-0 shrink-0"
          >
            All Quizzes <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        {/* Date tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-1 scrollbar-none">
          {days.map((d) => (
            <button
              key={d}
              onClick={() => handleDateChange(d)}
              className={[
                "shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-all",
                activeDate === d
                  ? "bg-violet-600 text-white border-violet-600 shadow-sm"
                  : "bg-white text-slate-500 border-slate-200 hover:border-violet-300 hover:text-violet-600",
              ].join(" ")}
            >
              {chipLabel(d, todayStr)}
            </button>
          ))}
        </div>

        {/* Card — constrained width so it doesn't stretch full page */}
        <div className="max-w-md">
          {loading ? (
            <QuizCardSkeleton />
          ) : notFound || !quiz ? (
            <EmptyQuizCard dateLabel={displayLabel} />
          ) : (
            <ActiveQuizCard quiz={quiz} />
          )}
        </div>
      </div>
    </section>
  );
}
