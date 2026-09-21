/**
 * /topics — the whole syllabus as one outline (G3.14e, ISR).
 *
 * Used to ask the topics API for a single page (capped at 100 rows) and hand
 * a flat list to a client-side filter grid — 100 of ~1,550 topics, no
 * hierarchy. It now renders what /subjects and /modules/<slug> render, all at
 * once: every subject → its modules → topics and subtopics, with the same
 * reading-list rows and ready-state marks, from the same cached subject trees.
 *
 * Data: the subject list plus one tree per subject (Redis-cached upstream —
 * the same calls the header and the subject cards already make). An API
 * outage aborts the regeneration rather than caching a partial syllabus.
 */

import { BookOpen, Layers } from "lucide-react";
import Link from "next/link";

import TopicOutline from "@/components/syllabus/topic-outline";
import { getBookSubjects, getBookTree } from "@/lib/api/book-content";
import { modulePath, nodeSegment, subjectPath } from "@/lib/content-urls";
import { abortIfApiUnreachable } from "@/lib/isr-guard";
import { buildMetadata } from "@/lib/seo/metadata";
import { countWithContent, flattenTopics } from "@/lib/syllabus-tree";
import type { SubjectTree } from "@/types/book-content";

// Hourly, as before: the outline gains rows as the pipeline generates.
export const revalidate = 3600;

export const metadata = buildMetadata({
  title: "Every UPSC CSE Topic — the full syllabus outline",
  description:
    "The complete UPSC Civil Services syllabus on one page — every subject, module, topic and subtopic in reading order, each linked to its study article.",
  path: "/topics",
});

async function fetchTrees(): Promise<SubjectTree[]> {
  try {
    const subjects = await getBookSubjects();
    const trees = await Promise.all(subjects.map((s) => getBookTree(s.id)));
    return trees;
  } catch (error) {
    // Outage → abort the ISR write; a 4xx yields an empty outline, which is
    // an answer (the same rule as /subjects and the detail pages).
    abortIfApiUnreachable(error, "Syllabus trees (/topics)");
    return [];
  }
}

export default async function TopicsPage() {
  const trees = await fetchTrees();

  const totals = trees.reduce(
    (acc, tree) => {
      const topics = tree.modules.flatMap((m) => flattenTopics(m.topics));
      acc.modules += tree.modules.length;
      acc.topics += topics.length;
      acc.ready += topics.filter((t) => t.has_content).length;
      return acc;
    },
    { modules: 0, topics: 0, ready: 0 },
  );

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      {/* Header — the same voice as /subjects */}
      <header className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <BookOpen className="h-8 w-8 text-primary" />
          <h1 className="text-4xl font-bold font-heading tracking-tight text-foreground">
            Topics
          </h1>
        </div>
        <p className="text-muted-foreground text-lg">
          Every UPSC topic, organised by subject and module — the whole syllabus
          in reading order.
        </p>
        {trees.length > 0 && (
          <p className="mt-3 text-sm text-muted-foreground">
            {trees.length} subjects · {totals.modules} modules · {totals.topics}{" "}
            topics ·{" "}
            <span className="font-semibold text-foreground">
              {totals.ready}
            </span>{" "}
            articles ready
          </p>
        )}
      </header>

      {trees.length === 0 ? (
        <div className="text-center py-20 bg-muted/40 rounded-lg border border-dashed border-border">
          <p className="text-muted-foreground font-medium">
            The syllabus is loading — try again in a moment.
          </p>
        </div>
      ) : (
        <>
          {/* Jump list — 14 subjects, one line each */}
          <nav
            aria-label="Subjects on this page"
            className="mb-10 flex flex-wrap gap-2"
          >
            {trees.map((tree) => (
              <a
                key={tree.id}
                href={`#${nodeSegment(tree)}`}
                className="rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
              >
                {tree.name}
              </a>
            ))}
          </nav>

          {trees.map((tree) => {
            const subjectTopics = tree.modules.flatMap((m) =>
              flattenTopics(m.topics),
            );
            const subjectReady = subjectTopics.filter(
              (t) => t.has_content,
            ).length;
            return (
              <section
                key={tree.id}
                id={nodeSegment(tree)}
                className="mb-12 scroll-mt-24"
              >
                <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-border pb-3">
                  <h2 className="text-2xl font-semibold text-foreground">
                    <Link
                      href={subjectPath(tree)}
                      className="hover:text-primary transition-colors"
                    >
                      {tree.name}
                    </Link>
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    {tree.modules.length} modules ·{" "}
                    <span className="font-semibold text-foreground">
                      {subjectReady}
                    </span>{" "}
                    of {subjectTopics.length} articles ready
                  </p>
                </div>

                {tree.modules.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No modules mapped to this subject yet.
                  </p>
                ) : (
                  tree.modules.map((mod) => {
                    const total = flattenTopics(mod.topics).length;
                    const ready = countWithContent(mod.topics);
                    return (
                      <div key={mod.id} className="mb-6">
                        <h3 className="mb-1 flex flex-wrap items-baseline gap-x-3 text-base font-semibold text-foreground">
                          <Link
                            href={modulePath(mod)}
                            className="inline-flex items-center gap-1.5 hover:text-primary transition-colors"
                          >
                            <Layers className="h-4 w-4 text-primary/70" />
                            {mod.name}
                          </Link>
                          {total > 0 && (
                            <span className="text-xs font-normal text-muted-foreground">
                              {ready} of {total} ready
                            </span>
                          )}
                        </h3>
                        {mod.topics.length === 0 ? (
                          <p className="ml-6 text-sm text-muted-foreground">
                            No topics mapped to this module yet.
                          </p>
                        ) : (
                          <TopicOutline topics={mod.topics} />
                        )}
                      </div>
                    );
                  })
                )}
              </section>
            );
          })}
        </>
      )}
    </div>
  );
}
