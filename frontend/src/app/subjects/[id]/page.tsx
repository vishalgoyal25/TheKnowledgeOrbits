/**
 * /subjects/<slug> — one subject of the syllabus (G3.13, ISR).
 *
 * Modules as cards, each with its ready / total article count derived from
 * the subject tree, so the page shows the syllabus content that exists — not
 * the generated-article count that was always zero.
 */

import { BookOpen, ChevronRight, Layers } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { permanentRedirect } from "next/navigation";

import { BreadcrumbJsonLd } from "@/components/seo/JsonLd";
import SyllabusBreadcrumb from "@/components/syllabus/syllabus-breadcrumb";
import { getBookTree } from "@/lib/api/book-content";
import { subjectsAPI } from "@/lib/api/subjects";
import { isUuid, modulePath, subjectPath } from "@/lib/content-urls";
import { buildMetadata, NOINDEX } from "@/lib/seo/metadata";
import { countWithContent, flattenTopics } from "@/lib/syllabus-tree";
import type { Subject } from "@/lib/types";
import type { SubjectTree } from "@/types/book-content";

// Revalidate daily — syllabus subjects rarely change; hourly rebuilds across
// many dynamic pages wasted Vercel ISR-write quota.
export const revalidate = 86400;

// G3.4
export async function generateMetadata(props: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await props.params;
  try {
    const subject: Subject | null = await subjectsAPI.getById(id);
    if (!subject) return NOINDEX;
    return buildMetadata({
      title: `${subject.name} — UPSC CSE Syllabus`,
      description:
        subject.description ||
        `${subject.name} for UPSC CSE: every module and topic with AI-generated study articles.`,
      path: subjectPath(subject),
    });
  } catch {
    return NOINDEX;
  }
}

export default async function SubjectPage(props: {
  params: Promise<{ id: string }>;
}) {
  const params = await props.params;
  // Slug or UUID (G3.10) — the API resolves either; the tree needs the UUID.
  const segment = params.id;
  let subject: Subject | null = null;
  let tree: SubjectTree | null = null;

  try {
    subject = await subjectsAPI.getById(segment);
    if (subject) tree = await getBookTree(subject.id);
  } catch (error) {
    if (process.env.SKIP_BACKEND_WAIT !== "true") {
      console.error(`Failed to fetch subject details: ${error}`);
    }
  }

  // Legacy UUID address → canonical slug address (308). Outside the try so
  // the redirect throw is never mistaken for a fetch failure.
  if (subject && isUuid(segment) && subject.slug) {
    permanentRedirect(subjectPath(subject));
  }

  if (!subject) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-muted-foreground">
        <h1 className="text-3xl font-semibold uppercase tracking-tight">
          Subject Not Found
        </h1>
        <p className="mt-4">The subject you are looking for does not exist.</p>
      </div>
    );
  }

  const modules = tree?.modules ?? [];
  const allTopics = modules.flatMap((m) => flattenTopics(m.topics));
  const readyAll = allTopics.filter((t) => t.has_content).length;

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {tree && (
        <>
          <BreadcrumbJsonLd
            items={[
              { name: "Syllabus", path: "/subjects" },
              { name: tree.name, path: subjectPath(tree) },
            ]}
          />
          <SyllabusBreadcrumb
            trail={[{ id: tree.id, slug: tree.slug, name: tree.name }]}
          />
        </>
      )}

      {/* Header */}
      <header className="mb-10 pb-6 border-b border-border">
        <div className="flex items-center gap-3 text-primary mb-3">
          <BookOpen className="h-9 w-9" />
          <h1 className="text-4xl md:text-5xl font-semibold font-heading tracking-tight text-foreground">
            {subject.name}
          </h1>
        </div>
        <p className="text-muted-foreground text-lg md:text-xl max-w-3xl">
          {subject.description ||
            "Browse the modules mapped within this core subject."}
        </p>
        {allTopics.length > 0 && (
          <p className="mt-3 text-sm text-muted-foreground">
            {modules.length} modules ·{" "}
            <span className="font-semibold text-foreground">{readyAll}</span> of{" "}
            {allTopics.length} articles ready
          </p>
        )}
      </header>

      {/* Module cards */}
      {modules.length === 0 ? (
        <div className="text-center py-20 bg-muted/40 rounded-lg border border-dashed border-border">
          <p className="text-muted-foreground font-medium">
            No modules available for this subject yet.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {modules.map((m) => {
            const total = flattenTopics(m.topics).length;
            const ready = countWithContent(m.topics);
            const pct = total ? Math.round((ready / total) * 100) : 0;
            return (
              <Link
                key={m.id}
                href={modulePath(m)}
                className="group rounded-xl border border-border bg-card p-6 transition-all hover:shadow-lg hover:-translate-y-0.5 hover:border-primary/40 flex flex-col"
              >
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-lg font-semibold text-foreground leading-snug group-hover:text-primary">
                    {m.name}
                  </h2>
                  <Layers className="h-5 w-5 text-primary/70 flex-shrink-0" />
                </div>
                <p className="mt-3 text-sm text-muted-foreground">
                  {m.topics.length} topics · {total} articles in total
                </p>
                <div className="mt-4">
                  <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                    <span>
                      <span className="font-semibold text-foreground">
                        {ready}
                      </span>{" "}
                      of {total} ready
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
                <span className="mt-5 inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wider text-primary">
                  Browse topics
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
