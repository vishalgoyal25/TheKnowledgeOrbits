import type { MetadataRoute } from "next";

import { absoluteUrl } from "@/lib/seo/site";

/**
 * /robots.txt (G3.2)
 *
 * Public content is crawlable; per-user, auth, admin and tool surfaces are
 * not — they are thin duplicate shells that would dilute crawl budget and
 * could index a login page. `/api/` is Next's own route handlers (revalidate).
 * Page-level `noindex` (G3.6) is the second, independent guard on the same
 * routes: robots stops the crawl, noindex stops indexing of anything that
 * gets crawled via a link anyway.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/admin",
          "/dashboard",
          "/profile",
          "/settings",
          "/notebook",
          "/bookmarks",
          "/generate",
          "/assessment",
          "/research_agent",
          "/auth",
          "/health",
          "/api/",
        ],
      },
    ],
    sitemap: absoluteUrl("/sitemap.xml"),
  };
}
