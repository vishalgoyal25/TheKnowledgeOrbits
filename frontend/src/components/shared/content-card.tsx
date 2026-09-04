import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The one card surface for public pages.
 *
 * Why this exists
 * ───────────────
 * The public pages carried three radii (rounded-xl / 2xl / 3xl) and three
 * surfaces (bg-white / bg-slate-50 / bg-slate-50-50) between them. Radius here
 * is `rounded-lg`, which Tailwind maps to `var(--radius)` — so the corner
 * decision lives in one CSS variable, not in every file that draws a box.
 *
 * Deliberately NOT a replacement for components/ui/card.tsx. That is the
 * shadcn primitive used inside app surfaces; this is the page-level content
 * surface, and it composes the same tokens so the two never disagree.
 */

type CardTone = "default" | "muted" | "accent";

const TONES: Record<CardTone, string> = {
  default: "bg-card border-border",
  muted: "bg-muted/40 border-transparent",
  /** Reserved for the single highlighted item in a group — never several. */
  accent: "bg-card border-primary/40",
};

interface ContentCardProps {
  children: ReactNode;
  tone?: CardTone;
  /** Adds hover affordance. Only set this when the whole card is clickable. */
  interactive?: boolean;
  className?: string;
}

export function ContentCard({
  children,
  tone = "default",
  interactive = false,
  className,
}: ContentCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border p-4 sm:p-5",
        TONES[tone],
        interactive &&
          "transition-colors hover:border-primary/40 hover:bg-accent/40",
        className,
      )}
    >
      {children}
    </div>
  );
}

interface ContentCardHeaderProps {
  title: ReactNode;
  /** Short qualifier — date, source, read time. */
  meta?: ReactNode;
  /** Leading visual. Keep to a 20px icon or a small badge. */
  icon?: ReactNode;
  className?: string;
}

export function ContentCardHeader({
  title,
  meta,
  icon,
  className,
}: ContentCardHeaderProps) {
  return (
    <div className={cn("flex items-start gap-3", className)}>
      {icon && (
        <span className="mt-0.5 shrink-0 text-muted-foreground">{icon}</span>
      )}
      <div className="min-w-0 flex-1">
        <h3 className="text-sm font-semibold leading-snug text-foreground sm:text-base">
          {title}
        </h3>
        {meta && <p className="mt-1 text-xs text-muted-foreground">{meta}</p>}
      </div>
    </div>
  );
}
