/**
 * Reusable Progress Bar Component
 */

import React from "react";
import { cn } from "@/lib/utils";

interface ProgressBarProps {
  value: number;
  max?: number;
  className?: string;
  barClassName?: string;
  showLabel?: boolean;
}

export default function ProgressBar({
  value,
  max = 100,
  className,
  barClassName,
  showLabel = false,
}: ProgressBarProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  return (
    <div className="w-full">
      <div
        className={cn(
          "w-full bg-gray-200 rounded-full h-2 overflow-hidden",
          className,
        )}
      >
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500 ease-out",
            barClassName,
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showLabel && (
        <div className="mt-1 text-right">
          <span className="text-xs font-semibold">
            {percentage.toFixed(0)}%
          </span>
        </div>
      )}
    </div>
  );
}
