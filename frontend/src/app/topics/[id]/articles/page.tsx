import { permanentRedirect } from "next/navigation";

/**
 * /topics/<slug>/articles → /topics/<slug> (G3.13).
 *
 * The topic page IS the article now; this suffix was a second URL for the
 * same subject — a duplicate to Google and a "0 articles / Generate" dead end
 * for readers. Every old link keeps working through the 308.
 */
export default async function TopicArticlesRedirect({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  permanentRedirect(`/topics/${id}`);
}
