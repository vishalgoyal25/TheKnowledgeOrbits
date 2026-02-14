/**
 * Quiz Listing Page
 * 
 * Browse and filter available quizzes.
 * Generate new quizzes for topics.
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuizzes, useGenerateQuiz } from '@/lib/hooks/use-quiz';
import QuizCard from '@/components/quiz/quiz-card';
import QuizFilters from '@/components/quiz/quiz-filters';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { FileQuestion, Plus } from 'lucide-react';

export default function AssessmentPage() {
  const [filters, setFilters] = useState({
    topic_id: '',
    difficulty: '' as '' | 'easy' | 'medium' | 'hard',
    include_ca: undefined as boolean | undefined,
  });

  const { data: quizzes, isLoading } = useQuizzes({
    topic_id: filters.topic_id || undefined,
    difficulty: filters.difficulty || undefined,
    include_ca: filters.include_ca,
  });

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="h-12 w-64 mb-8" />
        <Skeleton className="h-24 w-full mb-6" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <FileQuestion className="h-8 w-8 text-blue-600" />
            <h1 className="text-4xl font-bold">UPSC Quizzes</h1>
          </div>
          
          <Link href="/assessment/generate">
            <Button size="lg" className="gap-2">
              <Plus className="h-5 w-5" />
              Generate New Quiz
            </Button>
          </Link>
        </div>
        <p className="text-gray-600">
          Practice with AI-generated quizzes based on NCERT textbooks and current affairs
        </p>
      </div>

      {/* Filters */}
      <QuizFilters filters={filters} onFilterChange={setFilters} />

      {/* Quiz Grid */}
      {!quizzes || quizzes.length === 0 ? (
        <div className="text-center py-16 bg-gray-50 rounded-lg">
          <FileQuestion className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 text-lg mb-2">No quizzes found</p>
          <p className="text-sm text-gray-500 mb-4">
            Try adjusting your filters or generate a new quiz
          </p>
          <Link href="/assessment/generate">
            <Button className="gap-2">
              <Plus className="h-4 w-4" />
              Generate Quiz
            </Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {quizzes.map((quiz) => (
            <QuizCard key={quiz.id} quiz={quiz} />
          ))}
        </div>
      )}
    </div>
  );
}
