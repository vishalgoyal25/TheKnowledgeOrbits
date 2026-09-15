/**
 * /concepts/<slug> — server wrapper (G3.4 / G0.3 follow-up a).
 *
 * Was a "use client" page that fetched in the browser, so Google received an
 * empty shell for all 2,438 concept URLs and no per-page metadata could be
 * set. Now: the concept is fetched server-side (ISR, daily), the words are in
 * the HTML, and the page carries its own robots directive —
 *
 *   is_indexable (>= 400 words, >= 3 headings — the G0.3 rule, computed by
 *   the tags engine) → index; the ~818 that pass are also the ones the
 *   sitemap lists.
 *   otherwise (stub or thin)               → noindex, follow. Still reachable
 *   from every article that links it — readers use them — but Google is told
 *   not to judge the domain on them.
 *
 * The existing client component renders the page exactly as before; it just
 * receives the data as a prop instead of fetching it.
 */

import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ConceptDetailComponent } from "@/components/concepts/concept-detail";
import { ArticleJsonLd, BreadcrumbJsonLd } from "@/components/seo/JsonLd";
import ReadBeacon from "@/components/telemetry/ReadBeacon";
import { getConceptDetail, type ConceptDetail } from "@/lib/api/tags";
import { abortIfApiUnreachable } from "@/lib/isr-guard";
import { buildMetadata, NOINDEX } from "@/lib/seo/metadata";

// On-demand ISR: a concept page is built on first request and refreshed at
// most once a day. Nothing is prerendered at build (2,438 pages would be a
// regeneration wave on every deploy — C13); the long tail costs one write per
// page per day only when it is actually requested.
export const revalidate = 86400;

interface Props {
  params: Promise<{ slug: string }>;
}

/** 404 = no such concept (data); an outage aborts rather than caching a 404. */
async function fetchConcept(slug: string): Promise<ConceptDetail | null> {
  try {
    return await getConceptDetail(slug);
  } catch (error) {
    abortIfApiUnreachable(error, "Concept detail");
    return null;
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const concept = await fetchConcept(slug);
  if (!concept) return { title: "Concept not found", ...NOINDEX };
  return buildMetadata({
    title: `${concept.name} — UPSC Concept`,
    description:
      concept.brief_description ||
      `${concept.name}: a UPSC-relevant concept explained, with the current-affairs articles that reference it.`,
    path: `/concepts/${concept.slug}`,
    noindex: !concept.is_indexable,
    article: concept.is_indexable
      ? { publishedTime: concept.created_at, modifiedTime: concept.updated_at }
      : undefined,
  });
}

export default async function ConceptPage({ params }: Props) {
  const { slug } = await params;
  const concept = await fetchConcept(slug);
  if (!concept) notFound();

  return (
    <>
      {/* Beacon fires for stubs too: whether readers land on unfinished
          concept pages is exactly what G0.3 / G3.12 need to know. */}
      <ReadBeacon contentType="concept" contentId={concept.id} />
      <BreadcrumbJsonLd
        items={[
          { name: "Daily Current Affairs", path: "/daily-ca" },
          { name: concept.name, path: `/concepts/${concept.slug}` },
        ]}
      />
      {concept.is_indexable && (
        <ArticleJsonLd
          headline={concept.name}
          description={concept.brief_description || concept.name}
          path={`/concepts/${concept.slug}`}
          datePublished={concept.created_at}
          dateModified={concept.updated_at}
        />
      )}
      <ConceptDetailComponent concept={concept} />
    </>
  );
}
