/**
 * Question Display Component
 *
 * Renders question with options, handles multi-statement format.
 */

"use client";

import { useState } from "react";
import type { Question } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Flag, CheckCircle2, XCircle } from "lucide-react";

// ── Explanation helpers ───────────────────────────────────────────────────────

/**
 * Parse the LLM explanation string.
 * The LLM sometimes appends raw URLs after a "Source:" / "Sources Used:" label.
 * We extract them so they can be shown in a collapsible accordion instead of
 * appearing as plain text in the explanation body.
 */
function parseExplanation(text: string): { cleanText: string; urls: string[] } {
  if (!text) return { cleanText: "", urls: [] };

  const splitIdx = text.search(/\n*\s*Sources?\s*(Used)?:/i);
  if (splitIdx <= 0) return { cleanText: text.trim(), urls: [] };

  const cleanText = text.slice(0, splitIdx).trim();
  const urlBlock = text.slice(splitIdx);
  const urls = (urlBlock.match(/https?:\/\/[^\s\n]+/g) ?? []).filter(
    (u) => u.length > 10,
  );
  return { cleanText, urls };
}

/**
 * Add a blank line before each "Statement N:" occurrence and before
 * "Therefore," so multi-statement explanations are visually separated.
 */
function formatExplanationText(text: string): string {
  return text
    .replace(/(?<=[^\n])\s+(Statement\s+\d+:)/gi, "\n\n$1")
    .replace(/(?<=[^\n])\s+(Therefore[,\s])/gi, "\n\n$1")
    .trim();
}

// ── Inline sources accordion for quiz explanations ────────────────────────────

function getDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url.slice(0, 40);
  }
}

function QuizSourceAccordion({ urls }: { urls: string[] }) {
  const [open, setOpen] = useState(false);
  if (urls.length === 0) return null;

  return (
    <div className="mt-4 rounded-lg border border-blue-100 overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-blue-50/70 hover:bg-blue-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm">📰</span>
          <p className="text-xs font-semibold text-blue-800">
            News Sources &amp; Attribution
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-[11px] text-blue-500">
            {urls.length} source{urls.length !== 1 ? "s" : ""}
          </span>
          <span className="text-blue-400 text-xs">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {open && (
        <div className="divide-y divide-blue-50 bg-white">
          <p className="px-4 py-2 text-[11px] text-gray-400 border-b border-gray-50">
            This question was generated using the following news sources as
            context. All rights belong to the respective publishers.
          </p>
          {urls.map((url, i) => (
            <a
              key={i}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 px-4 py-2.5 hover:bg-blue-50 transition-colors group"
            >
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-100 text-[10px] text-blue-700 flex items-center justify-center font-bold">
                {i + 1}
              </span>
              <p className="flex-1 text-xs text-blue-700 truncate group-hover:text-blue-900">
                {getDomain(url)}
              </p>
              <span className="text-blue-300 text-xs group-hover:text-blue-500 transition-colors">
                ↗
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

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
  // Pre-parse explanation so the render section stays clean
  const { cleanText: explanationText, urls: explanationUrls } =
    parseExplanation(question.explanation ?? "");
  const formattedExplanation = formatExplanationText(explanationText);

  const renderQuestionText = () => {
    const text = (question.question_text ?? "").trim();
    const statements = question.statements ?? [];

    // Multi-statement: the backend is INCONSISTENT — sometimes it embeds the
    // numbered statements inside question_text, sometimes it keeps them only in
    // statements[]. To render reliably (context + clean numbered list) with no
    // duplication and no missing statements, we always derive the contextual
    // lead-in from question_text and render the statements from statements[].
    if (question.question_type === "multi_statement" && statements.length > 0) {
      // Lead-in = question_text up to the first embedded statement (if any),
      // dropping a dangling "1." / "1)" marker. If statements aren't embedded,
      // question_text IS the lead-in.
      let leadIn = text;
      const firstIdx = statements[0] ? text.indexOf(statements[0]) : -1;
      if (firstIdx > 0) {
        leadIn = text
          .slice(0, firstIdx)
          .replace(/\s*\d+[.)]\s*$/, "")
          .trim();
      }
      return (
        <div className="space-y-3">
          {leadIn && (
            <p className="whitespace-pre-wrap leading-relaxed font-medium">
              {leadIn}
            </p>
          )}
          <ol className="list-decimal list-inside space-y-2 ml-4">
            {statements.map((statement, idx) => (
              <li key={idx} className="text-gray-700">
                {statement}
              </li>
            ))}
          </ol>
        </div>
      );
    }

    // single_mcq / assertion_reasoning: question_text is the complete stem.
    return <p className="whitespace-pre-wrap leading-relaxed">{text}</p>;
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
        <RadioGroup value={selectedAnswer} className="space-y-3">
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

            {/* Formatted explanation — statements each on their own line */}
            <div className="prose prose-sm max-w-none text-blue-800 whitespace-pre-wrap leading-relaxed">
              {formattedExplanation}
            </div>

            {/* Collapsible sources accordion (URLs extracted from LLM text) */}
            <QuizSourceAccordion urls={explanationUrls} />

            {/* Fallback badge indicators when no raw URLs were embedded */}
            {explanationUrls.length === 0 &&
              (question.has_static_sources || question.has_ca_sources) && (
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
