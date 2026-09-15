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
 *   /topics/<slug> · /subjects/<slug> · /modules/<slug>   the ISR detail pages
 *
 * G3.10: hierarchy nodes carry a `slug` minted by the backend. Every builder
 * below prefers it and falls back to the UUID when it is absent, and every
 * route that consumes these URLs accepts either form — so nothing that was
 * ever shared breaks, and the site itself stops emitting UUIDs.
 */

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isIsoDate(value: string): boolean {
  return DATE_RE.test(value);
}

export function isUuid(value: string): boolean {
  return UUID_RE.test(value);
}

/** A node that may or may not have been given a slug yet. */
export interface SluggedRef {
  id: string;
  slug?: string | null;
}

/** The segment the site should emit for a node: its slug, else its UUID. */
export function nodeSegment(node: SluggedRef): string {
  return node.slug || node.id;
}

/** True when `segment` identifies `node` in either form. */
export function segmentMatches(segment: string, node: SluggedRef): boolean {
  return segment === node.id || (!!node.slug && segment === node.slug);
}

export function topicPath(node: SluggedRef): string {
  return `/topics/${nodeSegment(node)}`;
}

export function subjectPath(node: SluggedRef): string {
  return `/subjects/${nodeSegment(node)}`;
}

export function modulePath(node: SluggedRef): string {
  return `/modules/${nodeSegment(node)}`;
}

export function dailyCaArticlePath(slug: string): string {
  return `/daily-ca/${slug}`;
}

/** Slugs are minted as `<YYYY-MM-DD>-<title>`, so the date is the first 10 chars. */
export function dateFromDailyCaSlug(slug: string): string {
  return slug.slice(0, 10);
}

/**
 * Knowledge-map address. Accepts a node ref (slug preferred) or a bare
 * segment string — the header and the map both call this, and the map
 * sometimes only holds an id until the tree has loaded.
 */
export function knowledgePath(
  subject: SluggedRef | string | null | undefined,
  topic?: SluggedRef | string | null,
): string {
  const s =
    typeof subject === "string" ? subject : subject && nodeSegment(subject);
  if (!s) return "/knowledge";
  const t = typeof topic === "string" ? topic : topic && nodeSegment(topic);
  return t ? `/knowledge/${s}/${t}` : `/knowledge/${s}`;
}
