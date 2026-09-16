import type { MetadataRoute } from "next";

import { absoluteUrl } from "@/lib/seo/site";

/**
 * /sitemap.xml (G3.1)
 *
 * Composes three engine-local feeds — each engine lists only the URLs it owns,
 * so no engine reads another's tables:
 *   /knowledge/sitemap/   subjects · modules · topics   (slugs only)
 *   /daily-ca/sitemap/    every published article
 *   /concepts/sitemap/    the CURATED subset — the G0.3 rule (>= 400 words,
 *                         >= 3 headings) applied server-side, ~818 of 2,438
 *
 * Only canonical (slug) URLs are listed; a row with no slug is skipped by the
 * feed, never emitted as a UUID. Static and hub pages are listed by hand (15).
 *
 * Cost: `revalidate = 86400` keeps this a static route rebuilt once a day —
 * ~1 ISR write/day. It must never become dynamic (C2): a sitemap that renders
 * per request would be a function invocation for every crawler hit.
 *
 * A feed outage is not swallowed into an empty sitemap: the fetch throws, the
 * build aborts, and the last good sitemap keeps serving.
 */

export const revalidate = 86400;

const API =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ||
  "http://localhost:8000/api/v1";

interface Entry {
  slug: string;
  lastmod: string;
}

interface KnowledgeFeed {
  subjects: Entry[];
  modules: Entry[];
  topics: Entry[];
}

async function feed<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { next: { revalidate: 86400 } });
  if (!res.ok) {
    throw new Error(`sitemap feed ${path} responded ${res.status}`);
  }
  return res.json() as Promise<T>;
}

const STATIC: MetadataRoute.Sitemap = [
  { url: absoluteUrl("/"), changeFrequency: "daily", priority: 1 },
  { url: absoluteUrl("/subjects"), changeFrequency: "weekly", priority: 0.9 },
  { url: absoluteUrl("/daily-ca"), changeFrequency: "daily", priority: 0.9 },
  { url: absoluteUrl("/knowledge"), changeFrequency: "weekly", priority: 0.7 },
  { url: absoluteUrl("/topics"), changeFrequency: "weekly", priority: 0.6 },
  {
    url: absoluteUrl("/current-affairs"),
    changeFrequency: "daily",
    priority: 0.6,
  },
  // Public hubs found missing on the first production read (2026-09-16).
  // Their UUID detail pages (/current-affairs/<id>, /articles/<id>) stay out
  // by decision — thin, unslugged, reachable by links.
  { url: absoluteUrl("/news"), changeFrequency: "daily", priority: 0.6 },
  { url: absoluteUrl("/articles"), changeFrequency: "weekly", priority: 0.5 },
  {
    url: absoluteUrl("/current-affairs/chunks"),
    changeFrequency: "weekly",
    priority: 0.4,
  },
  {
    url: absoluteUrl("/current-affairs/sources"),
    changeFrequency: "weekly",
    priority: 0.4,
  },
  { url: absoluteUrl("/about"), changeFrequency: "monthly", priority: 0.4 },
  { url: absoluteUrl("/contact"), changeFrequency: "monthly", priority: 0.3 },
  { url: absoluteUrl("/privacy"), changeFrequency: "yearly", priority: 0.2 },
  { url: absoluteUrl("/terms"), changeFrequency: "yearly", priority: 0.2 },
  { url: absoluteUrl("/cookies"), changeFrequency: "yearly", priority: 0.2 },
];

function rows(
  entries: Entry[],
  prefix: string,
  changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"],
  priority: number,
): MetadataRoute.Sitemap {
  return entries.map((e) => ({
    url: absoluteUrl(`${prefix}/${e.slug}`),
    lastModified: e.lastmod,
    changeFrequency,
    priority,
  }));
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  let knowledge: KnowledgeFeed;
  let dailyCa: Entry[];
  let concepts: Entry[];
  try {
    [knowledge, dailyCa, concepts] = await Promise.all([
      feed<KnowledgeFeed>("/knowledge/sitemap/"),
      feed<Entry[]>("/daily-ca/sitemap/"),
      feed<Entry[]>("/concepts/sitemap/"),
    ]);
  } catch (error) {
    // Local / CI builds run with no reachable backend on purpose (same flag
    // the ISR guard honours). Emit the static pages only and say so loudly —
    // this branch must never be reached on Vercel, where a feed outage
    // should fail the deploy rather than publish a sitemap missing 2,000 URLs.
    if (process.env.SKIP_BACKEND_WAIT === "true") {
      console.warn(
        "sitemap: backend unreachable under SKIP_BACKEND_WAIT — static pages only",
      );
      return STATIC;
    }
    throw error;
  }

  return [
    ...STATIC,
    ...rows(knowledge.subjects, "/subjects", "weekly", 0.8),
    ...rows(knowledge.modules, "/modules", "weekly", 0.7),
    ...rows(knowledge.topics, "/topics", "weekly", 0.7),
    ...rows(dailyCa, "/daily-ca/article", "monthly", 0.6),
    ...rows(concepts, "/concepts", "monthly", 0.5),
  ];
}
