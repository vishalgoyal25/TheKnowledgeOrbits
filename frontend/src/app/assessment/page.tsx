/**
 * Quiz Listing Page
 *
 * Browse and filter available quizzes.
 * Generate new quizzes for topics.
 */

"use client";

import ProtectedRoute from "@/components/auth/ProtectedRoute";
import QuizCard from "@/components/quiz/quiz-card";
import QuizFilters from "@/components/quiz/quiz-filters";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useQuizzes } from "@/lib/hooks/use-quiz";
import { FileQuestion, History, LayoutGrid, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

export default function AssessmentPage() {
  const [, setActiveTab] = useState("grid");
  const [filters, setFilters] = useState({
    topic_id: "",
    difficulty: "" as "" | "easy" | "medium" | "hard",
    include_ca: undefined as boolean | undefined,
  });

  const { data: quizzes, isLoading } = useQuizzes({
    topic_id: filters.topic_id || undefined,
    difficulty: filters.difficulty || undefined,
    include_ca: filters.include_ca,
  });

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="container mx-auto px-4 py-8">
          <Skeleton className="h-12 w-64 mb-8" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <Skeleton key={i} className="h-64" />
            ))}
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  const quizzesData = quizzes || [];
  const uniqueTopics = new Set(quizzesData.map((q) => q.topic.id)).size;

  return (
    <ProtectedRoute>
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <FileQuestion className="h-8 w-8 text-blue-600" />
              <h1 className="text-4xl font-bold">Quizzes</h1>
            </div>

            <div className="flex gap-3">
              <Link href="/assessment/generate">
                <Button className="gap-2">
                  <Plus className="h-5 w-5" />
                  Generate New Quiz
                </Button>
              </Link>
            </div>
          </div>
          <p className="text-gray-600">
            Practice with AI-generated quizzes based on NCERT textbooks and
            current affairs
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="text-sm text-gray-600">Total Quizzes</div>
            <div className="text-3xl font-bold text-blue-600">
              {quizzesData.length}
            </div>
          </div>

          <div className="bg-green-50 rounded-lg p-4">
            <div className="text-sm text-gray-600">Active Topics</div>
            <div className="text-3xl font-bold text-green-600">
              {uniqueTopics}
            </div>
          </div>

          <div className="bg-purple-50 rounded-lg p-4">
            <div className="text-sm text-gray-600">Showing</div>
            <div className="text-3xl font-bold text-purple-600">
              {quizzesData.length}
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-8">
          <QuizFilters filters={filters} onFilterChange={setFilters} />
        </div>

        {/* View Toggle */}
        <Tabs
          defaultValue="grid"
          className="w-full"
          onValueChange={setActiveTab}
        >
          <TabsList className="mb-6">
            <TabsTrigger value="grid" className="gap-2">
              <LayoutGrid className="h-4 w-4" />
              Grid
            </TabsTrigger>
            <TabsTrigger value="timeline" className="gap-2">
              <History className="h-4 w-4" />
              Timeline
            </TabsTrigger>
          </TabsList>

          <TabsContent value="grid">
            {!quizzesData || quizzesData.length === 0 ? (
              <div className="text-center py-16 bg-gray-50 rounded-lg">
                <FileQuestion className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600 text-lg mb-2">No quizzes found</p>
                <Link href="/assessment/generate">
                  <Button className="gap-2">
                    <Plus className="h-4 w-4" />
                    Generate Quiz
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {quizzesData.map((quiz) => (
                  <QuizCard key={quiz.id} quiz={quiz} />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="timeline">
            {!quizzesData || quizzesData.length === 0 ? (
              <div className="text-center py-16 bg-gray-50 rounded-lg">
                <History className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">No quiz history found</p>
              </div>
            ) : (
              <div className="space-y-4">
                {quizzesData
                  .sort(
                    (a, b) =>
                      new Date(b.created_at).getTime() -
                      new Date(a.created_at).getTime(),
                  )
                  .map((quiz) => (
                    <Link
                      key={quiz.id}
                      href={`/assessment/${quiz.id}`}
                      className="block p-4 border rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-semibold">{quiz.title}</h3>
                          <p className="text-sm text-gray-500">
                            {quiz.topic.name} • {quiz.question_count} questions
                          </p>
                        </div>
                        <div className="text-sm text-gray-400">
                          {new Date(quiz.created_at).toLocaleDateString()}
                        </div>
                      </div>
                    </Link>
                  ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </ProtectedRoute>
  );
}
