"use client";

import Link from "next/link";
import { QuizAttempt } from "@/lib/types";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Clock, CheckCircle2, AlertCircle, RotateCcw } from "lucide-react";

interface AttemptCardProps {
  attempt: QuizAttempt;
}

export default function AttemptCard({ attempt }: AttemptCardProps) {
  const isSubmitted = attempt.status === "submitted";
  const score = attempt.score !== null ? Math.round(attempt.score) : 0;
  const startedAt = new Date(attempt.started_at).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case "submitted":
        return "bg-green-100 text-green-800 border-green-200";
      case "active":
        return "bg-blue-100 text-blue-800 border-blue-200";
      case "abandoned":
        return "bg-red-100 text-red-800 border-red-200";
      case "expired":
        return "bg-gray-100 text-gray-800 border-gray-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex justify-between items-start gap-2">
          <CardTitle className="text-base font-medium line-clamp-2">
            {attempt.quiz.title}
          </CardTitle>
          <Badge className={getStatusColor(attempt.status)} variant="outline">
            {attempt.status.charAt(0).toUpperCase() + attempt.status.slice(1)}
          </Badge>
        </div>
        <div className="text-sm text-muted-foreground">
          {attempt.quiz.topic.name}
        </div>
      </CardHeader>

      <CardContent className="pb-3">
        <div className="grid grid-cols-1 gap-2 text-sm">
          <div className="flex items-center gap-2 text-gray-500">
            <Clock className="h-4 w-4" />
            <span>{startedAt}</span>
          </div>

          {isSubmitted ? (
            <div className="flex items-center gap-2 font-medium">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              <span>Score: {score}%</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-blue-500" />
              <span>In Progress</span>
            </div>
          )}
        </div>
      </CardContent>

      <CardFooter>
        {isSubmitted ? (
          <Button asChild variant="outline" className="w-full gap-2">
            <Link href={`/assessment/${attempt.quiz.id}`}>
              <RotateCcw className="h-4 w-4" />
              Retake Quiz
            </Link>
          </Button>
        ) : (
          <Button asChild className="w-full gap-2">
            <Link href={`/assessment/${attempt.quiz.id}`}>Resume Quiz</Link>
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
