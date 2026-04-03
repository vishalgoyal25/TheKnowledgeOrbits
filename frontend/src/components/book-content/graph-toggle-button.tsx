"use client";

/**
 * GraphToggleButton — Toggles between Outline (navbar tree) and Graph (D3) views.
 *
 * - Persists state in localStorage key: "tko_view_mode"
 * - Default on first visit: "outline"
 * - Uses lucide-react Eye / List icons (already installed)
 */

import { Eye, List } from "lucide-react";
import { cn } from "@/lib/utils";

export type ViewMode = "outline" | "graph";

interface GraphToggleButtonProps {
  mode: ViewMode;
  onChange: (mode: ViewMode) => void;
  className?: string;
}

export const VIEW_MODE_KEY = "tko_view_mode";

export default function GraphToggleButton({
  mode,
  onChange,
  className,
}: GraphToggleButtonProps) {
  const isGraph = mode === "graph";

  function handleToggle() {
    const next: ViewMode = isGraph ? "outline" : "graph";
    onChange(next);
    try {
      localStorage.setItem(VIEW_MODE_KEY, next);
    } catch {
      // localStorage unavailable (SSR / private mode) — silently ignore
    }
  }

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-lg border border-border bg-muted/30 p-0.5",
        className,
      )}
      role="group"
      aria-label="Switch view mode"
    >
      {/* Outline button */}
      <button
        onClick={() => {
          if (isGraph) handleToggle();
        }}
        aria-pressed={!isGraph}
        title="Outline view — collapsible topic tree"
        className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
          !isGraph
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        <List className="h-3.5 w-3.5" />
        <span>Outline</span>
      </button>

      {/* Graph button */}
      <button
        onClick={() => {
          if (!isGraph) handleToggle();
        }}
        aria-pressed={isGraph}
        title="Graph view — interactive knowledge graph"
        className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
          isGraph
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        <Eye className="h-3.5 w-3.5" />
        <span>Graph</span>
      </button>
    </div>
  );
}
