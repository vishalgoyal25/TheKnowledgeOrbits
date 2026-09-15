import { DailyCaFeed } from "@/components/daily-ca/daily-ca-feed";
import { buildMetadata } from "@/lib/seo/metadata";

/**
 * /daily-ca/ — Today's daily current affairs feed.
 * DailyCaFeed handles data fetching client-side.
 */

export const metadata = buildMetadata({
  title: "Daily Current Affairs for UPSC",
  description:
    "Read today's UPSC-curated Current Affairs articles — GS-mapped, concept-linked, and ready for revision.",
  path: "/daily-ca",
});

export default function DailyCaPage() {
  return <DailyCaFeed />;
}
