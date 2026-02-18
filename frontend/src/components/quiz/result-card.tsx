'use client';

import { QuizAttempt } from '@/lib/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { CheckCircle2, XCircle, MinusCircle, Clock } from 'lucide-react';

interface ResultCardProps {
    attempt: QuizAttempt;
}

export default function ResultCard({ attempt }: ResultCardProps) {
    const score = attempt.score !== null ? Math.round(attempt.score) : 0;
    const accuracy = Math.round(attempt.accuracy);
    const total = attempt.correct_count + attempt.wrong_count + attempt.unanswered_count;

    const getScoreColor = (s: number) => {
        if (s >= 80) return 'text-green-600';
        if (s >= 50) return 'text-yellow-600';
        return 'text-red-600';
    };

    const getScoreBg = (s: number) => {
        if (s >= 80) return 'bg-green-50 border-green-200';
        if (s >= 50) return 'bg-yellow-50 border-yellow-200';
        return 'bg-red-50 border-red-200';
    };

    return (
        <Card className={`border-2 ${getScoreBg(score)}`}>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{attempt.quiz.title}</CardTitle>
                    <Badge variant="outline" className="text-xs">
                        {attempt.quiz.topic.name}
                    </Badge>
                </div>
            </CardHeader>

            <CardContent className="space-y-4">
                {/* Score Display */}
                <div className="text-center py-4">
                    <div className={`text-5xl font-extrabold ${getScoreColor(score)}`}>{score}%</div>
                    <p className="text-sm text-gray-500 mt-1">Final Score</p>
                    <Progress value={score} className="mt-3 h-3" />
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-3 gap-3 text-center text-sm">
                    <div className="bg-green-50 rounded-lg p-3">
                        <CheckCircle2 className="h-5 w-5 text-green-500 mx-auto mb-1" />
                        <div className="font-bold text-green-700">{attempt.correct_count}</div>
                        <div className="text-xs text-green-600">Correct</div>
                    </div>
                    <div className="bg-red-50 rounded-lg p-3">
                        <XCircle className="h-5 w-5 text-red-500 mx-auto mb-1" />
                        <div className="font-bold text-red-700">{attempt.wrong_count}</div>
                        <div className="text-xs text-red-600">Wrong</div>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-3">
                        <MinusCircle className="h-5 w-5 text-gray-400 mx-auto mb-1" />
                        <div className="font-bold text-gray-600">{attempt.unanswered_count}</div>
                        <div className="text-xs text-gray-500">Skipped</div>
                    </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between text-xs text-gray-400 pt-2 border-t">
                    <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        <span>{attempt.time_spent ? `${Math.round(attempt.time_spent / 60)} min` : 'N/A'}</span>
                    </div>
                    <span>Accuracy: {accuracy}%</span>
                    <span>{total} questions</span>
                </div>
            </CardContent>
        </Card>
    );
}
