/**
 * Exam Interface Page
 *
 * The "Exam Hall" - Take quiz with timer, question palette, navigation.
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuiz, useStartQuiz, useSubmitQuiz } from "@/lib/hooks/use-quiz";
import QuestionDisplay from "@/components/quiz/question-display";
import QuestionPalette from "@/components/quiz/question-palette";
import Timer from "@/components/quiz/timer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { ArrowLeft, ArrowRight, Send } from "lucide-react";
import Link from "next/link";
import type { QuizState } from "@/lib/types";

export default function TakeQuizPage() {
  const params = useParams();
  const router = useRouter();
  const quizId = params.id as string;

  const { data: quiz, isLoading } = useQuiz(quizId);
  const startQuizMutation = useStartQuiz();
  const submitQuizMutation = useSubmitQuiz();

  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [showSubmitDialog, setShowSubmitDialog] = useState(false);

  // Quiz state
  const [state, setState] = useState<QuizState>({
    currentQuestionIndex: 0,
    answers: {},
    questionTimes: {},
    markedForReview: new Set(),
    visitedQuestions: new Set([0]),
  });

  // Question start times (for time tracking)
  const [questionStartTime, setQuestionStartTime] = useState<number>(() =>
    Date.now(),
  );

  // Start quiz on mount
  useEffect(() => {
    if (quiz && !attemptId && !startQuizMutation.isPending) {
      startQuizMutation.mutate(quizId, {
        onSuccess: (attempt) => {
          setAttemptId(attempt.id);
        },
      });
    }
  }, [quiz, quizId, attemptId, startQuizMutation]);

  // Track time spent on current question
  useEffect(() => {
    setQuestionStartTime(Date.now());
  }, [state.currentQuestionIndex]);

  // Handlers
  const handleAnswerChange = useCallback(
    (questionId: string, answer: string) => {
      setState((prev) => ({
        ...prev,
        answers: { ...prev.answers, [questionId]: answer },
      }));
    },
    [],
  );

  const handleMarkForReview = useCallback((questionId: string) => {
    setState((prev) => {
      const newMarked = new Set(prev.markedForReview);
      if (newMarked.has(questionId)) {
        newMarked.delete(questionId);
      } else {
        newMarked.add(questionId);
      }
      return { ...prev, markedForReview: newMarked };
    });
  }, []);

  const navigateToQuestion = useCallback(
    (index: number) => {
      // Save time spent on current question
      const timeSpent = Math.floor((Date.now() - questionStartTime) / 1000);
      const currentQuestionId =
        quiz?.questions?.[state.currentQuestionIndex]?.id;

      if (currentQuestionId) {
        setState((prev) => ({
          ...prev,
          questionTimes: {
            ...prev.questionTimes,
            [currentQuestionId]:
              (prev.questionTimes[currentQuestionId] || 0) + timeSpent,
          },
          currentQuestionIndex: index,
          visitedQuestions: new Set([...prev.visitedQuestions, index]),
        }));
      }
    },
    [quiz, state.currentQuestionIndex, questionStartTime],
  );

  const handlePrevious = () => {
    if (state.currentQuestionIndex > 0) {
      navigateToQuestion(state.currentQuestionIndex - 1);
    }
  };

  const handleNext = () => {
    if (quiz && state.currentQuestionIndex < quiz.question_count - 1) {
      navigateToQuestion(state.currentQuestionIndex + 1);
    }
  };

  const handleSubmit = () => {
    if (!attemptId || !quiz) return;

    // Save time for current question
    const timeSpent = Math.floor((Date.now() - questionStartTime) / 1000);
    const currentQuestionId = quiz.questions?.[state.currentQuestionIndex]?.id;

    const finalTimes = { ...state.questionTimes };
    if (currentQuestionId) {
      finalTimes[currentQuestionId] =
        (finalTimes[currentQuestionId] || 0) + timeSpent;
    }

    // Build answers array
    const answers = quiz.questions!.map((q) => ({
      question_id: q.id,
      selected_option: state.answers[q.id] || "",
      time_spent: finalTimes[q.id] || 0,
      marked_for_review: state.markedForReview.has(q.id),
    }));

    submitQuizMutation.mutate(
      { attempt_id: attemptId, answers },
      {
        onSuccess: (result) => {
          setShowSubmitDialog(false);
          router.push(`/assessment/results/${result.id}`);
        },
      },
    );
  };

  const handleTimerExpire = () => {
    // Auto-submit when time expires
    handleSubmit();
  };

  if (isLoading || !quiz) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <Skeleton className="h-12 w-full mb-6" />
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3">
            <Skeleton className="h-96 w-full" />
          </div>
          <div className="lg:col-span-1">
            <Skeleton className="h-96 w-full" />
          </div>
        </div>
      </div>
    );
  }

  const currentQuestion = quiz.questions?.[state.currentQuestionIndex];
  const answeredCount = Object.keys(state.answers).filter(
    (k) => state.answers[k],
  ).length;
  const markedCount = state.markedForReview.size;

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      {/* Back button */}
      <Link href="/assessment">
        <Button variant="ghost" className="mb-4 gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Quizzes
        </Button>
      </Link>

      {/* Quiz Header */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-2xl">{quiz.title}</CardTitle>
              <p className="text-sm text-gray-600 mt-1">
                Question {state.currentQuestionIndex + 1} of{" "}
                {quiz.question_count}
              </p>
            </div>

            {quiz.time_limit && (
              <Timer
                initialSeconds={quiz.time_limit}
                onExpire={handleTimerExpire}
              />
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between text-sm">
            <div className="flex gap-4">
              <span className="text-green-600 font-medium">
                Answered: {answeredCount}
              </span>
              <span className="text-blue-600 font-medium">
                Marked: {markedCount}
              </span>
              <span className="text-gray-600 font-medium">
                Unanswered: {quiz.question_count - answeredCount}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Question Area */}
        <div className="lg:col-span-3 space-y-6">
          {currentQuestion && (
            <QuestionDisplay
              question={currentQuestion}
              questionNumber={state.currentQuestionIndex + 1}
              selectedAnswer={state.answers[currentQuestion.id] || ""}
              isMarked={state.markedForReview.has(currentQuestion.id)}
              onAnswerChange={(answer) =>
                handleAnswerChange(currentQuestion.id, answer)
              }
              onMarkToggle={() => handleMarkForReview(currentQuestion.id)}
            />
          )}

          {/* Navigation Buttons */}
          <div className="flex items-center justify-between">
            <Button
              onClick={handlePrevious}
              disabled={state.currentQuestionIndex === 0}
              variant="outline"
              className="gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Previous
            </Button>

            <div className="flex gap-3">
              {state.currentQuestionIndex === quiz.question_count - 1 ? (
                <Button
                  onClick={() => setShowSubmitDialog(true)}
                  size="lg"
                  className="gap-2"
                >
                  <Send className="h-5 w-5" />
                  Submit Quiz
                </Button>
              ) : (
                <Button
                  onClick={handleNext}
                  variant="default"
                  className="gap-2"
                >
                  Next
                  <ArrowRight className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Question Palette (Sidebar) */}
        <div className="lg:col-span-1">
          <QuestionPalette
            questions={quiz.questions || []}
            currentIndex={state.currentQuestionIndex}
            answers={state.answers}
            markedQuestions={state.markedForReview}
            visitedQuestions={state.visitedQuestions}
            onNavigate={navigateToQuestion}
          />
        </div>
      </div>

      {/* Submit Confirmation Dialog */}
      <AlertDialog open={showSubmitDialog} onOpenChange={setShowSubmitDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Submit Quiz?</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2" asChild>
              <div className="text-sm text-muted-foreground">
                <p>Are you sure you want to submit your quiz?</p>
                <div className="bg-gray-50 p-3 rounded-md text-sm space-y-1 my-2">
                  <p>✅ Answered: {answeredCount}</p>
                  <p>⚠️ Unanswered: {quiz.question_count - answeredCount}</p>
                  <p>🚩 Marked for Review: {markedCount}</p>
                </div>
                <p className="text-xs text-gray-600">
                  You cannot change your answers after submission.
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={submitQuizMutation.isPending}>
              Review Answers
            </AlertDialogCancel>
            <Button
              onClick={(e) => {
                e.preventDefault();
                handleSubmit();
              }}
              disabled={submitQuizMutation.isPending}
            >
              {submitQuizMutation.isPending ? "Submitting..." : "Submit"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
