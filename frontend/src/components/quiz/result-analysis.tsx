/**
 * Result Analysis Component
 *
 * Comprehensive score breakdown with performance insights.
 */

"use client";

import type { QuizAttempt } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Trophy,
  Target,
  Clock,
  TrendingUp,
  CheckCircle,
  XCircle,
} from "lucide-react";

interface ResultAnalysisProps {
  attempt: QuizAttempt;
}

export default function ResultAnalysis({ attempt }: ResultAnalysisProps) {
  const percentage = attempt.score || 0;
  const totalQuestions = attempt.quiz.question_count;

  const getPerformanceBadge = () => {
    if (percentage >= 80) {
      return {
        text: "Excellent! 🎉",
        color: "bg-green-100 text-green-800 border-green-200",
        message: "Outstanding performance! Keep it up!",
      };
    }
    if (percentage >= 60) {
      return {
        text: "Good Job! 👍",
        color: "bg-blue-100 text-blue-800 border-blue-200",
        message: "Solid performance. Review the concepts you missed.",
      };
    }
    if (percentage >= 40) {
      return {
        text: "Keep Practicing 💪",
        color: "bg-yellow-100 text-yellow-800 border-yellow-200",
        message: "You're making progress. Focus on weak areas.",
      };
    }
    return {
      text: "Needs Improvement 📚",
      color: "bg-red-100 text-red-800 border-red-200",
      message: "Don't worry! Review the material and try again.",
    };
  };

  const performanceBadge = getPerformanceBadge();

  const formatTime = (seconds: number | null) => {
    if (!seconds) return "N/A";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="space-y-6">
      {/* Score Card */}
      <Card className="bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 border-2">
        <CardHeader>
          <div className="flex items-center gap-3">
            <Trophy className="h-8 w-8 text-yellow-600" />
            <CardTitle className="text-2xl">Quiz Results</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-center space-y-4">
            {/* Score */}
            <div>
              <div className="text-7xl font-bold text-blue-600 mb-2">
                {percentage.toFixed(1)}%
              </div>
              <Badge className={`text-lg px-4 py-1 ${performanceBadge.color}`}>
                {performanceBadge.text}
              </Badge>
              <p className="text-gray-600 mt-3">{performanceBadge.message}</p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-3 gap-4 mt-6">
              <div className="bg-white rounded-lg p-4 border">
                <div className="flex items-center justify-center gap-2 mb-2">
                  <CheckCircle className="h-5 w-5 text-green-600" />
                  <span className="text-2xl font-bold text-green-600">
                    {attempt.correct_count}
                  </span>
                </div>
                <div className="text-sm text-gray-600">Correct</div>
              </div>

              <div className="bg-white rounded-lg p-4 border">
                <div className="flex items-center justify-center gap-2 mb-2">
                  <XCircle className="h-5 w-5 text-red-600" />
                  <span className="text-2xl font-bold text-red-600">
                    {attempt.wrong_count}
                  </span>
                </div>
                <div className="text-sm text-gray-600">Wrong</div>
              </div>

              <div className="bg-white rounded-lg p-4 border">
                <div className="flex items-center justify-center gap-2 mb-2">
                  <Target className="h-5 w-5 text-gray-600" />
                  <span className="text-2xl font-bold text-gray-700">
                    {totalQuestions}
                  </span>
                </div>
                <div className="text-sm text-gray-600">Total</div>
              </div>
            </div>

            {/* Additional Stats */}
            <div className="grid grid-cols-2 gap-4 mt-4">
              {attempt.time_spent && (
                <div className="bg-white rounded-lg p-3 border">
                  <div className="flex items-center justify-center gap-2">
                    <Clock className="h-4 w-4 text-purple-600" />
                    <span className="text-sm text-gray-600">
                      Time: {formatTime(attempt.time_spent)}
                    </span>
                  </div>
                </div>
              )}

              <div className="bg-white rounded-lg p-3 border">
                <div className="flex items-center justify-center gap-2">
                  <TrendingUp className="h-4 w-4 text-blue-600" />
                  <span className="text-sm text-gray-600">
                    Accuracy: {attempt.accuracy.toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Question-wise Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Answer Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
            {attempt.responses?.map((response, idx) => (
              <div
                key={response.id}
                className={`flex items-center justify-center p-3 rounded-lg border-2 font-semibold ${
                  response.is_correct
                    ? "bg-green-50 border-green-300 text-green-700"
                    : response.selected_option
                      ? "bg-red-50 border-red-300 text-red-700"
                      : "bg-gray-50 border-gray-300 text-gray-500"
                }`}
              >
                <span className="text-sm">Q{idx + 1}</span>
                <span className="ml-2">
                  {response.is_correct
                    ? "✓"
                    : response.selected_option
                      ? "✗"
                      : "○"}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
