/**
 * Question Palette Component
 *
 * Grid navigation showing status of all questions.
 */

"use client";

import type { Question } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface QuestionPaletteProps {
  questions: Question[];
  currentIndex: number;
  answers: Record<string, string>;
  markedQuestions: Set<string>;
  visitedQuestions: Set<number>;
  onNavigate: (index: number) => void;
}

export default function QuestionPalette({
  questions,
  currentIndex,
  answers,
  markedQuestions,
  visitedQuestions,
  onNavigate,
}: QuestionPaletteProps) {
  const getQuestionStatus = (question: Question, index: number) => {
    const isAnswered = !!answers[question.id];
    const isMarked = markedQuestions.has(question.id);
    const isVisited = visitedQuestions.has(index);
    const isCurrent = index === currentIndex;

    if (isCurrent) return "current";
    if (isMarked) return "marked";
    if (isAnswered) return "answered";
    if (isVisited) return "visited";
    return "not-visited";
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "current":
        return "bg-blue-600 text-white border-blue-700";
      case "marked":
        return "bg-purple-100 text-purple-800 border-purple-300";
      case "answered":
        return "bg-green-100 text-green-800 border-green-300";
      case "visited":
        return "bg-orange-100 text-orange-800 border-orange-300";
      default:
        return "bg-white text-gray-700 border-gray-300 hover:bg-gray-50";
    }
  };

  return (
    <Card className="sticky top-4">
      <CardHeader>
        <CardTitle className="text-lg">Questions</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Legend */}
        <div className="mb-4 space-y-2 text-xs">
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded bg-green-100 border border-green-300" />
            <span>Answered</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded bg-purple-100 border border-purple-300" />
            <span>Marked</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded bg-orange-100 border border-orange-300" />
            <span>Visited</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded bg-white border border-gray-300" />
            <span>Not Visited</span>
          </div>
        </div>

        {/* Question Grid */}
        <div className="grid grid-cols-5 gap-2">
          {questions.map((question, index) => {
            const status = getQuestionStatus(question, index);
            const statusColor = getStatusColor(status);

            return (
              <button
                key={question.id}
                onClick={() => onNavigate(index)}
                className={cn(
                  "aspect-square rounded-md border-2 font-semibold text-sm transition-all",
                  "hover:scale-105 active:scale-95",
                  statusColor,
                )}
              >
                {index + 1}
              </button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
