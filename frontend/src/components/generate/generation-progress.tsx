"use client";

import { Progress } from "@/components/ui/progress";
import { Loader2, CheckCircle2, Sparkles } from "lucide-react";

interface GenerationProgressProps {
  isGenerating: boolean;
  progress?: number; // 0-100
  stage?: string;
}

const STAGES = [
  "Searching knowledge base...",
  "Retrieving relevant chunks...",
  "Synthesizing content with AI...",
  "Formatting article...",
  "Finalizing...",
];

export default function GenerationProgress({
  isGenerating,
  progress = 0,
  stage,
}: GenerationProgressProps) {
  if (!isGenerating) return null;

  const displayStage =
    stage || STAGES[Math.floor((progress / 100) * (STAGES.length - 1))];

  return (
    <div className="w-full space-y-4 p-6 bg-blue-50 border border-blue-100 rounded-xl">
      <div className="flex items-center gap-3">
        {progress >= 100 ? (
          <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
        ) : (
          <Loader2 className="h-5 w-5 text-blue-600 animate-spin shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-medium text-blue-900 flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5" />
              {progress >= 100 ? "Article Generated!" : "Generating Article"}
            </span>
            <span className="text-xs text-blue-600 font-semibold">
              {Math.round(progress)}%
            </span>
          </div>
          <Progress value={progress} className="h-2 bg-blue-100" />
        </div>
      </div>
      <p className="text-xs text-blue-700 pl-8 animate-pulse">{displayStage}</p>
    </div>
  );
}
