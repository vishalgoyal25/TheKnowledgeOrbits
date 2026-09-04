import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Vertical rhythm + container width for every public page section.
 *
 * Why this exists
 * ───────────────
 * Home, about and contact each invented their own padding, max-width and
 * background. That is the mechanical half of why the pages feel unrelated:
 * even with identical cards inside, sections that breathe differently read as
 * different sites. Owning spacing in one place means a new section is
 * consistent by construction rather than by remembering.
 *
 * Mobile-first: py-10/px-4 is the design, the sm: and lg: steps are the
 * enhancement. Most UPSC traffic is on phones.
 */

type SectionTone = "default" | "muted";

interface SectionProps {
  children: ReactNode;
  /** "muted" gives the alternating band used to separate adjacent sections. */
  tone?: SectionTone;
  /** Anchor target for in-page links. */
  id?: string;
  /** Outer <section> overrides — background, borders, vertical padding. */
  className?: string;
  /** Inner container overrides — width, horizontal padding. */
  containerClassName?: string;
}

export function Section({
  children,
  tone = "default",
  id,
  className,
  containerClassName,
}: SectionProps) {
  return (
    <section
      id={id}
      className={cn(
        "py-10 sm:py-14",
        tone === "muted" && "bg-muted/40",
        className,
      )}
    >
      <div
        className={cn(
          "mx-auto w-full max-w-7xl px-4 sm:px-6",
          containerClassName,
        )}
      >
        {children}
      </div>
    </section>
  );
}

/**
 * Optional heading block for a Section. Kept separate so a section can carry a
 * heading, a custom header, or none at all without prop soup.
 */
interface SectionHeaderProps {
  title: string;
  description?: string;
  /** Right-aligned controls — date pickers, "view all" links. */
  action?: ReactNode;
  className?: string;
}

export function SectionHeader({
  title,
  description,
  action,
  className,
}: SectionHeaderProps) {
  return (
    <div
      className={cn(
        "mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
          {title}
        </h2>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
