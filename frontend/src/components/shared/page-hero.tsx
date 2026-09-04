import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The one hero for public pages.
 *
 * Why this shape (decision recorded 2026-09-04)
 * ─────────────────────────────────────────────
 * Three heroes existed: about was dark/glass, contact was light/tinted, home
 * was a gradient block. The chosen language is MINIMAL — typography on the
 * page surface, no decorative gradient band.
 *
 * The reason is measurable rather than aesthetic. The old home hero ran
 * `text-4xl sm:text-5xl lg:text-6xl` with `font-extrabold`; at 360px that
 * headline plus a gradient band consumed most of the first screen before
 * anything actionable appeared. Here the eyebrow, title, description and
 * actions all fit above the fold on a phone, which is where most UPSC traffic
 * is. Gradient is reserved for the primary CTA inside `actions` — one gradient,
 * in one place, so it reads as intent rather than decoration.
 */

interface PageHeroProps {
  title: ReactNode;
  /** Small label above the title — section name, date, category. */
  eyebrow?: ReactNode;
  description?: ReactNode;
  /** Buttons or links. The primary action carries the accent; siblings stay quiet. */
  actions?: ReactNode;
  /**
   * Optional right-hand column (live previews, widgets).
   *
   * On mobile it renders ABOVE the text block by default — `order-first` on the
   * aside — because on the homepage that column holds the Daily-CA preview, and
   * leading with today's content beats leading with a pitch. Pass
   * `asideBelowOnMobile` to invert that for pages where the copy matters more.
   */
  aside?: ReactNode;
  asideBelowOnMobile?: boolean;
  className?: string;
}

export function PageHero({
  title,
  eyebrow,
  description,
  actions,
  aside,
  asideBelowOnMobile = false,
  className,
}: PageHeroProps) {
  return (
    <section className={cn("border-b border-border bg-background", className)}>
      <div className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 sm:py-14">
        <div
          className={cn(
            "flex flex-col gap-8",
            aside && "lg:flex-row lg:items-center lg:gap-12",
          )}
        >
          <div className={cn("min-w-0", aside && "lg:flex-1")}>
            {eyebrow && (
              <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {eyebrow}
              </p>
            )}

            <h1 className="text-2xl font-semibold leading-tight tracking-tight text-foreground sm:text-3xl lg:text-4xl">
              {title}
            </h1>

            {description && (
              <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
                {description}
              </p>
            )}

            {actions && (
              <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
                {actions}
              </div>
            )}
          </div>

          {aside && (
            <div
              className={cn(
                "min-w-0 lg:flex-1 lg:order-none",
                asideBelowOnMobile ? "order-last" : "order-first",
              )}
            >
              {aside}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
