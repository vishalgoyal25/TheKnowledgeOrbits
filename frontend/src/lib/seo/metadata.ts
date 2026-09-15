import type { Metadata } from "next";

import { absoluteUrl } from "@/lib/seo/site";

/**
 * Shared metadata builder (G3.4). Every public page calls this so title,
 * description, canonical, Open Graph and Twitter are set the same way once —
 * and a page that must stay out of the index says so with one flag.
 *
 * `title` is the page's own part; the root layout's template appends the
 * brand. `path` is the canonical path (slug form, never a UUID) — Next resolves
 * it against `metadataBase`.
 */
export interface PageMeta {
  title: string;
  description: string;
  /** Canonical path, e.g. "/topics/fundamental-rights". */
  path: string;
  /** Article pages: enables OG type=article and published/modified times. */
  article?: { publishedTime?: string; modifiedTime?: string; section?: string };
  /** Private or thin pages: keep out of the index, still crawlable. */
  noindex?: boolean;
  image?: string;
}

const TRIM = 160;

export function truncate(text: string, max = TRIM): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  return `${clean.slice(0, max - 1).replace(/\s+\S*$/, "")}…`;
}

export function buildMetadata(meta: PageMeta): Metadata {
  const description = truncate(meta.description);
  const url = absoluteUrl(meta.path);
  const images = meta.image ? [{ url: meta.image }] : undefined;

  return {
    title: meta.title,
    description,
    alternates: { canonical: meta.path },
    robots: meta.noindex
      ? { index: false, follow: true }
      : { index: true, follow: true },
    openGraph: {
      type: meta.article ? "article" : "website",
      url,
      title: meta.title,
      description,
      ...(images ? { images } : {}),
      ...(meta.article
        ? {
            publishedTime: meta.article.publishedTime,
            modifiedTime: meta.article.modifiedTime,
            section: meta.article.section,
          }
        : {}),
    },
    twitter: {
      card: images ? "summary_large_image" : "summary",
      title: meta.title,
      description,
      ...(images ? { images: images.map((i) => i.url) } : {}),
    },
  };
}

/** For the ~ten private route groups: one line each (G3.6). */
export const NOINDEX: Metadata = {
  robots: { index: false, follow: false },
};
