/**
 * Topic detail page (ISR/SSG)
 */

import ArticleCard from "@/components/articles/article-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { articlesAPI } from "@/lib/api/articles";
import { topicsAPI } from "@/lib/api/topics";
import { Article } from "@/lib/types";
import { ArrowLeft, BookOpen, Hash, Layers } from "lucide-react";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import { abortIfApiUnreachable } from "@/lib/isr-guard";
import { isUuid, nodeSegment, topicPath } from "@/lib/content-urls";

// Revalidate daily — topic content changes at most once/day, and there are
// ~1,462 topic pages; hourly rebuilds × that many pages was the dominant
// Vercel ISR-write cost. On-demand revalidation refreshes edits instantly.
export const revalidate = 86400;

// Pre-render topics for stability during build. G3.10: params are SLUGS
// (UUID only for a row not yet backfilled) — the address Google is told about.
export async function generateStaticParams() {
  try {
    const topics = await topicsAPI.list({ page_size: 200 });
    return (topics || []).map((topic) => ({ id: nodeSegment(topic) }));
  } catch (error) {
    // Returning [] used to be silent: the build stayed green and prerendered
    // NOTHING for this route, with no signal in the output (§5A.2). An outage
    // now fails the build; a 4xx still yields an empty list, which is an answer.
    abortIfApiUnreachable(error, "Topics list (generateStaticParams)");

    console.error(
      "BUILD WARNING: generateStaticParams for Topics returned no ids.",
      error,
    );
    return [];
  }
}

interface TopicPageProps {
  params: Promise<{ id: string }>;
}

export default async function TopicDetailPage({ params }: TopicPageProps) {
  // The segment is a slug or a UUID (G3.10); the API resolves either.
  const { id: segment } = await params;

  try {
    const topic = await topicsAPI.getById(segment);

    if (!topic) {
      return notFound();
    }

    // A UUID address for a topic that has a slug is the legacy form: send the
    // visitor (and the crawler) to the canonical one. 308, cached like any
    // other ISR result for that path. permanentRedirect throws — the catch
    // below rethrows anything that is not an API error, so it propagates.
    if (isUuid(segment) && topic.slug) {
      permanentRedirect(topicPath(topic));
    }

    // The article filter needs the UUID, so it follows the topic fetch.
    const articlesData = await articlesAPI.listByTopic(topic.id);
    const articles = articlesData?.results || [];

    return (
      <div className="container mx-auto px-4 py-8">
        {/* Back button */}
        <div className="mb-8">
          <Link href="/topics">
            <Button variant="ghost" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Back to Topics
            </Button>
          </Link>
        </div>

        {/* Topic Header */}
        <div className="mb-8 p-8 bg-white rounded-xl border shadow-sm transition-all hover:shadow-md">
          <div className="flex justify-between items-start gap-4 mb-6">
            <div>
              <div className="flex items-center gap-3 mb-3 text-sm font-medium text-muted-foreground uppercase tracking-widest">
                <span className="flex items-center gap-1.5 transition-colors hover:text-blue-600 cursor-default">
                  <BookOpen className="h-4 w-4" />
                  {topic.subject_name}
                </span>
                <span>•</span>
                <span className="flex items-center gap-1.5 transition-colors hover:text-indigo-600 cursor-default">
                  <Layers className="h-4 w-4" />
                  {topic.module_name}
                </span>
              </div>
              <h1 className="text-4xl font-semibold text-foreground leading-tight">
                {topic.name}
              </h1>
            </div>
            <Badge
              variant={
                topic.topic_type === "syllabus" ? "default" : "secondary"
              }
              className="text-xs px-3 py-1 uppercase font-bold"
            >
              {topic.topic_type}
            </Badge>
          </div>

          {topic.description && (
            <p className="text-muted-foreground text-lg mb-8 leading-relaxed max-w-4xl">
              {topic.description}
            </p>
          )}

          {topic.keywords && topic.keywords.length > 0 && (
            <div className="flex items-start gap-3 border-t pt-6 bg-muted/40/50 p-4 rounded-lg">
              <Hash className="h-5 w-5 mt-0.5 text-muted-foreground" />
              <div className="flex flex-wrap gap-2.5">
                {topic.keywords.map((kw, i) => (
                  <Badge
                    key={i}
                    variant="outline"
                    className="bg-white px-3 py-1 font-medium transition-colors hover:border-blue-300"
                  >
                    {kw}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Articles Section */}
        <div className="space-y-8">
          <div className="flex items-center justify-between border-b pb-4">
            <h2 className="text-3xl font-semibold text-foreground font-heading">
              Study Materials
            </h2>
            {articles.length > 0 && (
              <span className="bg-blue-100 text-blue-700 font-bold px-4 py-1.5 rounded-full text-sm">
                {articles.length} RELEVANT ARTICLE
                {articles.length !== 1 ? "S" : ""}
              </span>
            )}
          </div>

          {articles.length === 0 ? (
            <div className="text-center py-20 bg-muted/40/50 rounded-xl border border-dashed border-gray-300">
              <div className="max-w-md mx-auto">
                <p className="text-muted-foreground text-lg mb-6">
                  Our AI engines haven't generated specialized study material
                  for this topic yet.
                </p>
                <Link href={`/generate?topic=${topic.id}`}>
                  <Button
                    size="lg"
                    className="px-8 shadow-lg shadow-blue-500/20 active:scale-95 transition-transform"
                  >
                    ✨ Generate Intelligence
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {articles.map((article: Article) => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          )}
        </div>
      </div>
    );
  } catch (error) {
    // An outage (no response / 5xx) aborts rather than caching an error page.
    // The red "Error retrieving topic" box that used to be returned here was
    // prerendered and cached for 24 h, so a transient API failure during one
    // build served a permanent error to every visitor of that topic (§5A.4a).
    abortIfApiUnreachable(error, "Topics API");

    // 4xx: the API answered and this topic is gone. Data, not an outage — one
    // missing topic must not fail a build that prerenders ~100 of them.
    console.warn(`Topic ${segment} unavailable — rendering 404.`);
    notFound();
  }
}
