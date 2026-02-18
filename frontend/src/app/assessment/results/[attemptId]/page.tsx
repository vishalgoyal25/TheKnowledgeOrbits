/**
 * Results Analysis Page
 * 
 * Detailed breakdown with explanations and source citations.
 */

'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useAttemptResult } from '@/lib/hooks/use-quiz';
import ResultAnalysis from '@/components/quiz/result-analysis';
import QuestionDisplay from '@/components/quiz/question-display';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, RotateCcw, BookOpen } from 'lucide-react';

export default function QuizResultsPage() {
  const params = useParams();
  const attemptId = params.attemptId as string;

  const { data: attempt, isLoading } = useAttemptResult(attemptId);

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-5xl">
        <Skeleton className="h-64 w-full mb-6" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!attempt) {
    return (
      <div className="container mx-auto px-4 py-8 text-center">
        <p className="text-gray-600">Results not found</p>
        <Link href="/assessment">
          <Button variant="outline" className="mt-4">
            Back to Quizzes
          </Button>
        </Link>
      </div>
    );
  }

  // Build answer map for displaying user's choices
  const answerMap = attempt.responses?.reduce((acc, response) => {
    acc[response.question] = response.selected_option;
    return acc;
  }, {} as Record<string, string>) || {};

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      {/* Back button */}
      <Link href="/assessment">
        <Button variant="ghost" className="mb-6 gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Quizzes
        </Button>
      </Link>

      {/* Results Analysis */}
      <ResultAnalysis attempt={attempt} />

      {/* Review Section */}
      <div className="mt-8">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">Review Your Answers</CardTitle>
            <p className="text-sm text-gray-600">
              Study the explanations to understand where you went wrong
            </p>
          </CardHeader>
        </Card>

        <div className="mt-6 space-y-8">
          {attempt.questions_with_answers?.map((question, idx) => {
            const response = attempt.responses?.find(
              (r) => r.question === question.id
            );

            return (
              <Card
                key={question.id}
                className={`border-l-4 ${response?.is_correct
                  ? 'border-l-green-500'
                  : response?.selected_option
                    ? 'border-l-red-500'
                    : 'border-l-gray-300'
                  }`}
              >
                <CardContent className="pt-6">
                  <QuestionDisplay
                    question={question}
                    questionNumber={idx + 1}
                    selectedAnswer={answerMap[question.id] || ''}
                    onAnswerChange={() => { }}
                    showAnswer={true}
                    showExplanation={true}
                    readOnly={true}
                  />

                  {/* Time spent */}
                  {response && response.time_spent > 0 && (
                    <p className="text-xs text-gray-500 mt-4">
                      Time spent: {Math.floor(response.time_spent / 60)}m{' '}
                      {response.time_spent % 60}s
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="mt-8 flex flex-col sm:flex-row gap-4">
        <Link href={`/assessment/${attempt.quiz.id}`} className="flex-1">
          <Button variant="outline" className="w-full gap-2">
            <RotateCcw className="h-4 w-4" />
            Retake Quiz
          </Button>
        </Link>

        {/* Link to article for this topic */}
        <Link
          href={`/articles?topic=${attempt.quiz.topic.id}`}
          className="flex-1"
        >
          <Button variant="default" className="w-full gap-2">
            <BookOpen className="h-4 w-4" />
            Learn More About {attempt.quiz.topic.name}
          </Button>
        </Link>

        <Link href="/assessment" className="flex-1">
          <Button className="w-full">Browse More Quizzes</Button>
        </Link>
      </div>
    </div>
  );
}
