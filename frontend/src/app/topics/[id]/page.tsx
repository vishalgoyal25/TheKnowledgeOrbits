/**
 * /topics/<slug> — the topic IS the article (G3.13, ISR).
 *
 * Renders, in the initial HTML:
 *   breadcrumb · the BookContent article body · the reading list of every
 *   subtopic beneath it (with article status) · the syllabus context.
 * No "Generate Article" — generation is a logged-in feature reached from the
 * sidebar, never advertised on a public page. Generated (user) articles are
 * private to their author's notebook and do not appear here.
 *
 * Data: the topic by slug-or-UUID, the subject tree (Redis-cached upstream)
 * for nesting + `has_content`, and the article by topic UUID.
 */

import { BookOpen, Layers } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";

import { ArticleJsonLd, BreadcrumbJsonLd } from "@/components/seo/JsonLd";
import ArticleBody from "@/components/syllabus/article-body";
import SyllabusBreadcrumb from "@/components/syllabus/syllabus-breadcrumb";
import TopicOutline from "@/components/syllabus/topic-outline";
import ReadBeacon from "@/components/telemetry/ReadBeacon";
import { getBookContent, getBookTree } from "@/lib/api/book-content";
import { topicsAPI } from "@/lib/api/topics";
import {
  isUuid,
  modulePath,
  nodeSegment,
  subjectPath,
  topicPath,
} from "@/lib/content-urls";
import { abortIfApiUnreachable } from "@/lib/isr-guard";
import { buildMetadata, NOINDEX, truncate } from "@/lib/seo/metadata";
import { findTopic, trailTo } from "@/lib/syllabus-tree";
import type { BookContent, SubjectTree } from "@/types/book-content";

// Revalidate weekly (was daily; raised 2026-09-18). A topic's article is
// locked once generated, so the page's only moving part is the reading list's
// ready-state, which can lag a week. After the sitemap went live, crawlers
// touch all ~1,550 topic pages, and each touch after expiry is an ISR write:
// daily windows across every content family ran the project at ~8–17k
// writes/day against a 200k/month allowance (§7.11). Raising is always
// allowed (C2 forbids lowering); on-demand revalidation can refresh instantly.
export const revalidate = 604800;

// Pre-render topics for stability during build. G3.10: params are SLUGS
// (UUID only for a row not yet backfilled) — the address Google is told about.
export async function generateStaticParams() {
  try {
    const topics = await topicsAPI.list({ page_size: 200 });
    return (topics || []).map((topic) => ({ id: nodeSegment(topic) }));
  } catch (error) {
    // Returning [] used to be silent: the build stayed green and prerendered
    // NOTHING for this route, with no signal in the output (§5A.2). An outage
    // now fails the build; a 4xx still yields an empty list, which is an answer.
    abortIfApiUnreachable(error, "Topics list (generateStaticParams)");

    console.error(
      "BUILD WARNING: generateStaticParams for Topics returned no ids.",
      error,
    );
    return [];
  }
}

interface TopicPageProps {
  params: Promise<{ id: string }>;
}

// G3.4 — title, description, canonical (slug form), OG/Twitter. The topic
// fetch is deduplicated with the page's own by Next's request memoisation.
export async function generateMetadata({
  params,
}: TopicPageProps): Promise<Metadata> {
  const { id: segment } = await params;
  try {
    const topic = await topicsAPI.getById(segment);
    if (!topic) return NOINDEX;
    return buildMetadata({
      title: `${topic.name} — ${topic.subject_name}`,
      description:
        topic.description ||
        `${topic.name}: a UPSC CSE study article under ${topic.module_name}, ${topic.subject_name}, with its subtopics and reading list.`,
      path: topicPath(topic),
      article: { section: topic.subject_name },
    });
  } catch {
    return NOINDEX;
  }
}

/** 404 from the content endpoint means "no article yet" — data, not an outage. */
async function fetchArticleOrNull(
  topicId: string,
): Promise<BookContent | null> {
  try {
    return await getBookContent(topicId);
  } catch (error) {
    abortIfApiUnreachable(error, "Book content");
    return null;
  }
}

export default async function TopicDetailPage({ params }: TopicPageProps) {
  // The segment is a slug or a UUID (G3.10); the API resolves either.
  const { id: segment } = await params;

  try {
    const topic = await topicsAPI.getById(segment);
    if (!topic) return notFound();

    // A UUID address for a topic that has a slug is the legacy form: send the
    // visitor (and the crawler) to the canonical one. 308, cached like any
    // other ISR result for that path. permanentRedirect throws — the catch
    // below rethrows anything that is not an API error, so it propagates.
    if (isUuid(segment) && topic.slug) {
      permanentRedirect(topicPath(topic));
    }

    const [tree, article]: [SubjectTree, BookContent | null] =
      await Promise.all([
        getBookTree(topic.subject),
        fetchArticleOrNull(topic.id),
      ]);
    const trail = trailTo(tree, topic.id);
    const node = tree.modules
      .map((m) => findTopic(m.topics, topic.id))
      .find((t) => t !== null);
    const subtopics = node?.subtopics ?? [];
    const path = topicPath(topic);

    // G3.5 — structured data, only for what is actually in this HTML.
    const breadcrumbItems = [
      { name: "Syllabus", path: "/subjects" },
      ...trail.map((crumb, i) => ({
        name: crumb.name,
        path:
          i === 0
            ? subjectPath(crumb)
            : i === 1
              ? modulePath(crumb)
              : topicPath(crumb),
      })),
    ];

    return (
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {trail.length > 0 && <BreadcrumbJsonLd items={breadcrumbItems} />}
        {article && (
          <ArticleJsonLd
            headline={topic.name}
            description={truncate(
              topic.description ||
                article.render_content.replace(/[#*_`>|-]/g, " "),
            )}
            path={path}
            datePublished={article.created_at}
            dateModified={article.updated_at}
            section={topic.subject_name}
          />
        )}

        {trail.length > 0 && <SyllabusBreadcrumb trail={trail} />}

        {/* ── Header ───────────────────────────────────────────────────── */}
        <header className="mb-8">
          <div className="flex items-center gap-3 mb-3 text-xs font-medium text-muted-foreground uppercase tracking-widest">
            <span className="flex items-center gap-1.5">
              <BookOpen className="h-4 w-4" />
              {topic.subject_name}
            </span>
            <span>•</span>
            <span className="flex items-center gap-1.5">
              <Layers className="h-4 w-4" />
              {topic.module_name}
            </span>
          </div>
          <h1 className="text-3xl md:text-4xl font-semibold text-foreground leading-tight">
            {topic.name}
          </h1>
          {!article && topic.description && (
            <p className="mt-4 text-muted-foreground text-lg leading-relaxed">
              {topic.description}
            </p>
          )}
        </header>

        {/* ── The article ───────────────────────────────────────────────── */}
        {article ? (
          <article className="mb-12">
            <ReadBeacon contentType="topic" contentId={topic.id} />
            <ArticleBody markdown={article.render_content} />
            <p className="mt-8 pt-4 border-t border-border/60 text-xs text-muted-foreground">
              {article.word_count.toLocaleString()} words ·{" "}
              {Math.max(1, Math.round(article.word_count / 200))} min read
            </p>
          </article>
        ) : (
          <div className="mb-12 rounded-xl border border-dashed border-border bg-muted/30 px-6 py-10 text-center">
            <p className="text-muted-foreground">
              The article for this topic is being written by the daily pipeline.
              Its subtopics below may already be ready.
            </p>
          </div>
        )}

        {/* ── Reading list ─────────────────────────────────────────────── */}
        {subtopics.length > 0 && (
          <section className="mb-12">
            <h2 className="text-xl font-semibold text-foreground mb-3">
              In this topic
            </h2>
            <TopicOutline topics={subtopics} />
          </section>
        )}

        {/* ── Where this sits ───────────────────────────────────────────── */}
        <nav className="flex flex-wrap gap-3 text-sm">
          <Link
            href={`/knowledge/${nodeSegment(tree)}/${nodeSegment(topic)}`}
            className="rounded-md border border-border px-3 py-1.5 text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors"
          >
            Open in the Knowledge Map →
          </Link>
        </nav>
      </div>
    );
  } catch (error) {
    // An outage (no response / 5xx) aborts rather than caching an error page.
    // The red "Error retrieving topic" box that used to be returned here was
    // prerendered and cached for 24 h, so a transient API failure during one
    // build served a permanent error to every visitor of that topic (§5A.4a).
    abortIfApiUnreachable(error, "Topics API");

    // 4xx: the API answered and this topic is gone. Data, not an outage — one
    // missing topic must not fail a build that prerenders ~100 of them.
    console.warn(`Topic ${segment} unavailable — rendering 404.`);
    notFound();
  }
}
