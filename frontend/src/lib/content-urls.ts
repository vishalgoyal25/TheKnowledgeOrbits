/**
 * Canonical URLs for the two reader surfaces that swap content in place.
 *
 * Both used to keep their state in a query string (?article=, ?topic=). GA4
 * strips query strings from its page-path dimension, so every article and
 * topic collapsed into one row. Paths survive intact — so the address bar,
 * the tracker and the share link now all carry the same thing.
 *
 *   /daily-ca/<slug>                 one article in the feed (slug starts with its date)
 *   /knowledge/<subject>/<topic>     one topic in the knowledge map
 *   /knowledge/<subject>             a subject with no topic open
 */

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export function isIsoDate(value: string): boolean {
  return DATE_RE.test(value);
}

export function dailyCaArticlePath(slug: string): string {
  return `/daily-ca/${slug}`;
}

/** Slugs are minted as `<YYYY-MM-DD>-<title>`, so the date is the first 10 chars. */
export function dateFromDailyCaSlug(slug: string): string {
  return slug.slice(0, 10);
}

export function knowledgePath(
  subjectId: string | null | undefined,
  topicId?: string | null,
): string {
  if (!subjectId) return "/knowledge";
  return topicId
    ? `/knowledge/${subjectId}/${topicId}`
    : `/knowledge/${subjectId}`;
}
