/**
 * Quiz Card Component
 * 
 * Preview card showing quiz details.
 */

'use client';

import Link from 'next/link';
import type { Quiz } from '@/lib/types';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Clock, FileQuestion, Target, Newspaper } from 'lucide-react';

interface QuizCardProps {
  quiz: Quiz;
}

export default function QuizCard({ quiz }: QuizCardProps) {
  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'easy':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'hard':
        return 'bg-red-100 text-red-800 border-red-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <Card className="h-full hover:shadow-lg transition-shadow duration-200">
      <CardHeader>
        <div className="flex items-start justify-between gap-2 mb-2">
          <CardTitle className="text-lg line-clamp-2 flex-1">
            {quiz.title}
          </CardTitle>
          <Badge className={getDifficultyColor(quiz.difficulty_level)}>
            {quiz.difficulty_level}
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-blue-600">
            {quiz.topic.name}
          </span>
          {quiz.include_ca && (
            <Badge variant="outline" className="text-xs gap-1">
              <Newspaper className="h-3 w-3" />
              CA
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent>
        <div className="space-y-3 text-sm">
          <div className="flex items-center gap-2 text-gray-600">
            <FileQuestion className="h-4 w-4 text-blue-600" />
            <span>{quiz.question_count} questions</span>
          </div>

          {quiz.time_limit && (
            <div className="flex items-center gap-2 text-gray-600">
              <Clock className="h-4 w-4 text-purple-600" />
              <span>{Math.floor(quiz.time_limit / 60)} minutes</span>
            </div>
          )}

          <div className="flex items-center gap-2 text-gray-600">
            <Target className="h-4 w-4 text-green-600" />
            <span>UPSC Pattern</span>
          </div>

          {quiz.include_ca && (
            <p className="text-xs text-gray-500 mt-2">
              Includes questions based on recent Current Affairs
            </p>
          )}
        </div>
      </CardContent>

      <CardFooter>
        <Link href={`/assessment/${quiz.id}`} className="w-full">
          <Button className="w-full">Start Quiz</Button>
        </Link>
      </CardFooter>
    </Card>
  );
}
