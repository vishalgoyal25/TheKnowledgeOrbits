/**
 * /subjects — the syllabus landing page (G3.13, ISR).
 *
 * Did not exist before (the route table had /subjects/[id] but no index).
 * Every subject as a card with its description and generated / planned topic
 * progress, in syllabus order, linking to /subjects/<slug>. The top of the
 * chain /subjects → /subjects/<slug> → /modules/<slug> → /topics/<slug>, and
 * the natural landing page for a "UPSC CSE syllabus" search.
 */

import { BookOpen, ChevronRight } from "lucide-react";
import Link from "next/link";

import { getBookSubjects } from "@/lib/api/book-content";
import { subjectPath } from "@/lib/content-urls";
import { abortIfApiUnreachable } from "@/lib/isr-guard";
import type { SubjectWithPlan } from "@/types/book-content";

export const revalidate = 86400;

export const metadata = {
  title: "UPSC CSE Syllabus — Subjects, Modules & Topics | TheKnowledgeOrbits",
  description:
    "The complete UPSC Civil Services syllabus as a connected map — every subject, module and topic, with AI-generated study articles for each.",
};

async function fetchSubjects(): Promise<SubjectWithPlan[]> {
  try {
    return await getBookSubjects();
  } catch (error) {
    // An outage aborts the build rather than caching an empty syllabus page.
    abortIfApiUnreachable(error, "Book subjects");
    return [];
  }
}

export default async function SubjectsIndexPage() {
  const subjects = await fetchSubjects();

  return (
    <div className="container mx-auto px-4 py-10 max-w-6xl">
      <header className="mb-10">
        <p className="text-xs font-bold uppercase tracking-widest text-primary mb-2">
          Syllabus
        </p>
        <h1 className="text-4xl md:text-5xl font-semibold font-heading tracking-tight text-foreground">
          UPSC CSE Syllabus
        </h1>
        <p className="mt-4 text-lg text-muted-foreground max-w-3xl">
          Every subject in the Civil Services syllabus, broken into modules and
          topics, each with an AI-generated study article. Pick a subject to
          start.
        </p>
      </header>

      {subjects.length === 0 ? (
        <div className="text-center py-20 bg-muted/40 rounded-lg border border-dashed border-border">
          <p className="text-muted-foreground font-medium">
            The syllabus is loading — try again in a moment.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {subjects.map((s) => {
            const planned = s.book_plan?.topics_planned ?? 0;
            const done = s.book_plan?.topics_completed ?? 0;
            const pct = planned ? Math.round((done / planned) * 100) : 0;
            return (
              <Link
                key={s.id}
                href={subjectPath(s)}
                className="group rounded-xl border border-border bg-card p-6 transition-all hover:shadow-lg hover:-translate-y-0.5 hover:border-primary/40 flex flex-col"
              >
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-lg font-semibold text-foreground leading-snug group-hover:text-primary">
                    {s.name}
                  </h2>
                  <BookOpen className="h-5 w-5 text-primary/70 flex-shrink-0" />
                </div>
                {s.description && (
                  <p className="mt-3 text-sm text-muted-foreground line-clamp-3">
                    {s.description}
                  </p>
                )}
                {planned > 0 && (
                  <div className="mt-4">
                    <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                      <span>
                        <span className="font-semibold text-foreground">
                          {done}
                        </span>{" "}
                        of {planned} articles
                      </span>
                      <span>{pct}%</span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-border overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )}
                <span className="mt-5 inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wider text-primary">
                  Browse modules
                  <ChevronRight className="h-3.5 w-3.5" />
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
