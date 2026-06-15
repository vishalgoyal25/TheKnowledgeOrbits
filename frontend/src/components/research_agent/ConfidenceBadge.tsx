"use client";

import { useEffect, useRef, useState } from "react";
import { CONFIDENCE_HIGH, CONFIDENCE_MED } from "@/lib/api/research-agent";

export interface ConfidenceBadgeProps {
  score: number | null; // null = DeepEval evaluation still running
}

const RADIUS = 20;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function scoreToColor(score: number): {
  ring: string;
  text: string;
  bg: string;
} {
  if (score >= CONFIDENCE_HIGH)
    return { ring: "#22c55e", text: "text-green-700", bg: "bg-green-50" };
  if (score >= CONFIDENCE_MED)
    return { ring: "#f97316", text: "text-orange-700", bg: "bg-orange-50" };
  return { ring: "#ef4444", text: "text-red-700", bg: "bg-red-50" };
}

export default function ConfidenceBadge({ score }: ConfidenceBadgeProps) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const rafRef = useRef<number | null>(null);

  // Animate from 0 → score over ~600ms when score first arrives.
  useEffect(() => {
    if (score === null) return;
    const finalScore = score; // capture narrowed value for closure
    const start = performance.now();
    const duration = 600;

    function step(now: number) {
      const progress = Math.min((now - start) / duration, 1);
      // Ease-out cubic.
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimatedScore(eased * finalScore);
      if (progress < 1) rafRef.current = requestAnimationFrame(step);
    }

    rafRef.current = requestAnimationFrame(step);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [score]);

  // ── Pending skeleton ────────────────────────────────────────────────────────
  if (score === null) {
    return (
      <div className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-gray-50 px-3 py-1.5">
        <div className="w-8 h-8 rounded-full bg-gray-200 animate-pulse" />
        <div className="flex flex-col gap-1">
          <div className="w-20 h-2.5 rounded bg-gray-200 animate-pulse" />
          <div className="w-14 h-2 rounded bg-gray-100 animate-pulse" />
        </div>
      </div>
    );
  }

  const pct = Math.round(score * 100);
  const colors = scoreToColor(score);
  const offset = CIRCUMFERENCE * (1 - animatedScore);

  return (
    <div
      title="Research Confidence: scored by AI judge on faithfulness, relevance, completeness and accuracy"
      className={[
        "inline-flex items-center gap-2.5 rounded-full border px-3 py-1.5 cursor-default select-none",
        "transition-colors duration-300",
        colors.bg,
        "border-current/20",
      ].join(" ")}
    >
      {/* Circular progress ring */}
      <svg
        width="36"
        height="36"
        viewBox="0 0 48 48"
        className="flex-shrink-0 -rotate-90"
      >
        {/* Track */}
        <circle
          cx="24"
          cy="24"
          r={RADIUS}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth="5"
        />
        {/* Animated fill */}
        <circle
          cx="24"
          cy="24"
          r={RADIUS}
          fill="none"
          stroke={colors.ring}
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.05s linear" }}
        />
      </svg>

      {/* Score text + label */}
      <div className="flex flex-col leading-tight">
        <span className={`text-sm font-semibold tabular-nums ${colors.text}`}>
          {pct}%
        </span>
        <span className="text-[10px] text-gray-500 font-medium uppercase tracking-wide">
          Research Confidence
        </span>
      </div>
    </div>
  );
}
