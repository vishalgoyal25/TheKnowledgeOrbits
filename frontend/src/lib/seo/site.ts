/**
 * The one place the site's public origin is decided (G3).
 *
 * `NEXT_PUBLIC_SITE_URL` is set in Vercel (Production). The fallback is the
 * canonical production host so a build with the variable missing still emits
 * absolute URLs that are right, never localhost. Used by sitemap.ts,
 * robots.ts, metadataBase and JSON-LD.
 */
export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL || "https://www.theknowledgeorbits.com"
).replace(/\/+$/, "");

export const SITE_NAME = "TheKnowledgeOrbits";

export function absoluteUrl(path: string): string {
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}
