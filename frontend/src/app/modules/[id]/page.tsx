/**
 * /modules/<slug> — one module of the syllabus (G3.13, ISR).
 *
 * Renders the module's topics as the NESTED tree they are — topic → subtopic
 * → sub-subtopic — with each node's article status, all in the initial HTML.
 * Replaces the flat card grid that showed every depth as a peer and counted
 * the wrong article table ("0 articles" on every card).
 */

import { Layers } from "lucide-react";
import type { Metadata } from "next";
import { permanentRedirect } from "next/navigation";

import { ArticleJsonLd, BreadcrumbJsonLd } from "@/components/seo/JsonLd";
import ArticleBody from "@/components/syllabus/article-body";
import SyllabusBreadcrumb from "@/components/syllabus/syllabus-breadcrumb";
import TopicOutline from "@/components/syllabus/topic-outline";
import { getBookTree, getOverview } from "@/lib/api/book-content";
import { subjectsAPI } from "@/lib/api/subjects";
import { isUuid, modulePath, subjectPath } from "@/lib/content-urls";
import { buildMetadata, NOINDEX, truncate } from "@/lib/seo/metadata";
import {
  countWithContent,
  findModule,
  flattenTopics,
  trailTo,
} from "@/lib/syllabus-tree";
import type { Module } from "@/lib/types";
import type { OverviewContent, SubjectTree } from "@/types/book-content";

// Revalidate daily — module structure rarely changes; hourly rebuilds across
// many dynamic pages wasted Vercel ISR-write quota.
export const revalidate = 86400;

// G3.4
export async function generateMetadata(props: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await props.params;
  try {
    const moduleData: Module | null = await subjectsAPI.getModuleById(id);
    if (!moduleData) return NOINDEX;
    return buildMetadata({
      title: `${moduleData.name} — UPSC CSE Syllabus`,
      description:
        moduleData.description ||
        `${moduleData.name}: every topic and subtopic in this UPSC CSE module, with AI-generated study articles.`,
      path: modulePath(moduleData),
    });
  } catch {
    return NOINDEX;
  }
}

export default async function ModulePage(props: {
  params: Promise<{ id: string }>;
}) {
  const params = await props.params;
  // Slug or UUID (G3.10) — the API resolves either; the tree fetch needs the
  // subject UUID, so it follows the module fetch.
  const segment = params.id;
  let moduleData: Module | null = null;
  let tree: SubjectTree | null = null;
  let overview: OverviewContent | null = null;

  try {
    moduleData = await subjectsAPI.getModuleById(segment);
    if (moduleData) {
      const subjectId =
        typeof moduleData.subject === "string"
          ? moduleData.subject
          : moduleData.subject.id;
      // G3.9 — the overview is null until its row is generated and published.
      [tree, overview] = await Promise.all([
        getBookTree(subjectId),
        getOverview("module", moduleData.id),
      ]);
    }
  } catch (error) {
    if (process.env.SKIP_BACKEND_WAIT !== "true") {
      console.error("Failed to fetch module details", error);
    }
  }

  // Legacy UUID address → canonical slug address (308). Outside the try so
  // the redirect throw is never mistaken for a fetch failure.
  if (moduleData && isUuid(segment) && moduleData.slug) {
    permanentRedirect(modulePath(moduleData));
  }

  if (!moduleData) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-muted-foreground">
        <h1 className="text-3xl font-semibold uppercase tracking-tight">
          Module Not Found
        </h1>
        <p className="mt-4">
          The module you&apos;re trying to view doesn&apos;t exist.
        </p>
      </div>
    );
  }

  const node = tree ? findModule(tree, moduleData.id) : null;
  const topics = node?.topics ?? [];
  const total = flattenTopics(topics).length;
  const ready = countWithContent(topics);
  const trail = tree ? trailTo(tree, moduleData.id) : [];

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      {trail.length > 0 && (
        <>
          <BreadcrumbJsonLd
            items={[
              { name: "Syllabus", path: "/subjects" },
              { name: trail[0].name, path: subjectPath(trail[0]) },
              { name: moduleData.name, path: modulePath(moduleData) },
            ]}
          />
          <SyllabusBreadcrumb trail={trail} />
        </>
      )}

      {/* Header */}
      <header className="mb-8 pb-6 border-b border-border">
        <div className="flex items-center gap-3 text-primary mb-3">
          <Layers className="h-8 w-8" />
          <h1 className="text-3xl md:text-4xl font-semibold font-heading tracking-tight text-foreground">
            {moduleData.name}
          </h1>
        </div>
        <p className="text-muted-foreground text-lg max-w-3xl">
          {moduleData.description ||
            "The syllabus topics inside this module, in reading order."}
        </p>
        {total > 0 && (
          <p className="mt-3 text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">{ready}</span> of{" "}
            {total} articles ready
          </p>
        )}
      </header>

      {/* G3.9 — introductory overview, server-rendered; absent until
          generated and published. */}
      {overview && (
        <section className="mb-10">
          <ArticleJsonLd
            headline={`${moduleData.name} — Overview`}
            description={truncate(overview.content_markdown)}
            path={modulePath(moduleData)}
            dateModified={overview.updated_at}
            section={trail[0]?.name}
          />
          <ArticleBody markdown={overview.content_markdown} />
        </section>
      )}

      {/* Nested outline */}
      {topics.length === 0 ? (
        <div className="text-center py-16 bg-muted/40 rounded-xl border border-dashed border-border">
          <p className="text-muted-foreground">
            No topics mapped to this module yet.
          </p>
        </div>
      ) : (
        <section>
          <h2 className="text-xl font-semibold text-foreground mb-3">Topics</h2>
          <TopicOutline topics={topics} />
        </section>
      )}
    </div>
  );
}
