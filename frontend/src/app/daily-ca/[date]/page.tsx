import { DailyCaFeed } from "@/components/daily-ca/daily-ca-feed";

/**
 * /daily-ca/[date]/ — Current affairs feed for a specific date (YYYY-MM-DD).
 */

interface Props {
  params: Promise<{ date: string }>;
}

export async function generateMetadata({ params }: Props) {
  const { date } = await params;
  return {
    title: `Current Affairs ${date} — TheKnowledgeOrbits`,
    description: `UPSC Current Affairs for ${date} — GS-mapped articles with concept links.`,
  };
}

export default async function DailyCaDatePage({ params }: Props) {
  const { date } = await params;
  return <DailyCaFeed date={date} />;
}
