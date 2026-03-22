/**
 * Question Display Component
 *
 * Renders question with options, handles multi-statement format.
 */

"use client";

import type { Question } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Flag, CheckCircle2, XCircle } from "lucide-react";

interface QuestionDisplayProps {
  question: Question;
  questionNumber: number;
  selectedAnswer: string;
  isMarked?: boolean;
  onAnswerChange: (answer: string) => void;
  onMarkToggle?: () => void;
  showAnswer?: boolean;
  showExplanation?: boolean;
  readOnly?: boolean;
}

export default function QuestionDisplay({
  question,
  questionNumber,
  selectedAnswer,
  isMarked = false,
  onAnswerChange,
  onMarkToggle,
  showAnswer = false,
  showExplanation = false,
  readOnly = false,
}: QuestionDisplayProps) {
  const renderQuestionText = () => {
    if (
      question.question_type === "multi_statement" &&
      question.statements.length > 0
    ) {
      return (
        <div className="space-y-3">
          <p className="font-medium">Consider the following statements:</p>
          <ol className="list-decimal list-inside space-y-2 ml-4">
            {question.statements.map((statement, idx) => (
              <li key={idx} className="text-gray-700">
                {statement}
              </li>
            ))}
          </ol>
          <p className="font-medium mt-4">Which of the above is/are correct?</p>
        </div>
      );
    }

    return <p className="whitespace-pre-wrap">{question.question_text}</p>;
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <CardTitle className="text-lg">
                Question {questionNumber}
              </CardTitle>
              <Badge variant="outline" className="text-xs">
                {question.question_type.replace("_", " ")}
              </Badge>
              <Badge
                variant="outline"
                className={`text-xs ${
                  question.difficulty_level === "hard"
                    ? "border-red-200 text-red-700"
                    : question.difficulty_level === "medium"
                      ? "border-yellow-200 text-yellow-700"
                      : "border-green-200 text-green-700"
                }`}
              >
                {question.difficulty_level}
              </Badge>
            </div>
            <div className="text-gray-700">{renderQuestionText()}</div>
          </div>

          {!readOnly && onMarkToggle && (
            <Button
              variant={isMarked ? "default" : "outline"}
              size="sm"
              onClick={onMarkToggle}
              className="gap-2"
            >
              <Flag className={`h-4 w-4 ${isMarked ? "fill-current" : ""}`} />
              {isMarked ? "Marked" : "Mark"}
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Options */}
        <RadioGroup
          value={selectedAnswer}
          className="space-y-3"
        >
          {Object.entries(question.options).map(([key, value]) => {
            const isCorrect = showAnswer && key === question.correct_answer;
            const isSelected = key === selectedAnswer;
            const isWrong = showAnswer && isSelected && !isCorrect;

            return (
              <div
                key={key}
                onClick={(e) => {
                  if (readOnly) return;
                  e.preventDefault(); // Prevent double triggers from label/radio defaults
                  if (isSelected) {
                    onAnswerChange(""); // Toggle off if already selected
                  } else {
                    onAnswerChange(key); // Select if not selected
                  }
                }}
                className={`flex items-start space-x-3 p-4 rounded-lg border-2 transition-all duration-75 cursor-pointer ${
                  isCorrect
                    ? "bg-green-50 border-green-300"
                    : isWrong
                      ? "bg-red-50 border-red-300"
                      : isSelected
                        ? "border-blue-300 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                }`}
              >
                <RadioGroupItem
                  value={key}
                  id={`${question.id}-${key}`}
                  disabled={readOnly}
                  className="mt-1"
                />
                <Label
                  htmlFor={`${question.id}-${key}`}
                  className="flex-1 cursor-pointer leading-relaxed"
                >
                  <span className="font-semibold mr-2">{key}.</span>
                  {value}
                </Label>

                {showAnswer && isCorrect && (
                  <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0" />
                )}
                {showAnswer && isWrong && (
                  <XCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
                )}
              </div>
            );
          })}
        </RadioGroup>

        {/* Explanation */}
        {showExplanation && question.explanation && (
          <div className="mt-6 p-5 bg-blue-50 rounded-lg border border-blue-200">
            <div className="flex items-center gap-2 mb-3">
              <div className="h-6 w-1 bg-blue-600 rounded-full" />
              <p className="font-semibold text-blue-900">Explanation</p>
            </div>
            <div className="prose prose-sm max-w-none text-blue-800 whitespace-pre-wrap">
              {question.explanation}
            </div>

            {/* Source indicators */}
            {(question.has_static_sources || question.has_ca_sources) && (
              <div className="mt-4 pt-4 border-t border-blue-200">
                <p className="text-xs text-blue-700 font-medium mb-2">
                  Sources Used:
                </p>
                <div className="flex gap-2">
                  {question.has_static_sources && (
                    <Badge variant="outline" className="text-xs">
                      📚 Textbook
                    </Badge>
                  )}
                  {question.has_ca_sources && (
                    <Badge variant="outline" className="text-xs">
                      📰 Current Affairs
                    </Badge>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
