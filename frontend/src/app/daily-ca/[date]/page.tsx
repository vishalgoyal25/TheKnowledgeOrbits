import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DailyCaFeed } from "@/components/daily-ca/daily-ca-feed";
import { dateFromDailyCaSlug, isIsoDate } from "@/lib/content-urls";
import { buildMetadata } from "@/lib/seo/metadata";

/**
 * /daily-ca/[date]/ — the current-affairs feed for one day.
 *
 * The segment is EITHER a date (YYYY-MM-DD) OR an article slug, which is
 * minted as `<YYYY-MM-DD>-<title>` and therefore carries its own date. Both
 * render the same feed for that date; with a slug, DailyCaFeed opens that
 * article instead of the first one. This is what makes `/daily-ca/<slug>`
 * survive a refresh after the feed pushed it into the address bar.
 *
 * `/daily-ca/article/<slug>` is a different, static route and wins over this
 * one — it is the standalone SEO page, not the feed.
 */

interface Props {
  params: Promise<{ date: string }>;
}

function resolveDate(segment: string): string | null {
  if (isIsoDate(segment)) return segment;
  const fromSlug = dateFromDailyCaSlug(segment);
  return isIsoDate(fromSlug) ? fromSlug : null;
}

// G3.4/G3.6 — the feed is a client-fetched shell (G0.1), so it is NOT the
// page Google should index. A slug address is the same article as
// /daily-ca/article/<slug>, which is server-rendered: point the canonical
// there and keep this shell out of the index. A date address is a browsing
// view: noindex, canonical to itself.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { date: segment } = await params;
  const decoded = decodeURIComponent(segment);
  const date = resolveDate(decoded) ?? decoded;
  const isSlug = !isIsoDate(decoded);
  return {
    ...buildMetadata({
      title: `Current Affairs ${date}`,
      description: `UPSC Current Affairs for ${date} — GS-mapped articles with concept links.`,
      path: isSlug ? `/daily-ca/article/${decoded}` : `/daily-ca/${date}`,
      noindex: true,
    }),
  };
}

export default async function DailyCaDatePage({ params }: Props) {
  const { date: segment } = await params;
  const date = resolveDate(decodeURIComponent(segment));
  if (!date) notFound();
  return <DailyCaFeed date={date} />;
}
