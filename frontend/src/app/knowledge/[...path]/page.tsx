import type { Metadata } from "next";
import { notFound } from "next/navigation";

import KnowledgeMapPage from "@/components/book-content/knowledge-map-page";
import { NOINDEX } from "@/lib/seo/metadata";

/**
 * /knowledge/[...path] — Knowledge Map with a selection in the URL.
 *
 *   /knowledge/<subject>          subject open, no topic
 *   /knowledge/<subject>/<topic>  topic open in the reader
 *
 * The same component as /knowledge; it reads the segments off usePathname.
 * This route exists so a URL the feed pushed into the address bar survives a
 * refresh, a bookmark, or a share. Anything deeper than two segments is not
 * an address we mint.
 */

interface Props {
  params: Promise<{ path: string[] }>;
}

// G3.6 — every deep-link is the same client-fetched shell as /knowledge with
// a selection; thousands of near-duplicates. The indexable page for a topic
// is /topics/<slug>. Keep these out of the index, canonical to the map root.
export const metadata: Metadata = {
  title: "Knowledge Map",
  description:
    "Browse the UPSC syllabus as a connected map — every subject, module and topic, with AI-generated articles one click away.",
  alternates: { canonical: "/knowledge" },
  ...NOINDEX,
};

export default async function KnowledgeDeepLinkPage({ params }: Props) {
  const { path } = await params;
  if (path.length > 2) notFound();
  return <KnowledgeMapPage />;
}
