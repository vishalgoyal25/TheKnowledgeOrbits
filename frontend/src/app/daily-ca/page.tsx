import { DailyCaFeed } from "@/components/daily-ca/daily-ca-feed";

/**
 * /daily-ca/ — Today's daily current affairs feed.
 * DailyCaFeed handles data fetching client-side.
 */

export const metadata = {
  title: "Daily Current Affairs — TheKnowledgeOrbits",
  description:
    "Read today's UPSC-curated Current Affairs articles — GS-mapped, concept-linked, and ready for revision.",
};

export default function DailyCaPage() {
  return <DailyCaFeed />;
}
