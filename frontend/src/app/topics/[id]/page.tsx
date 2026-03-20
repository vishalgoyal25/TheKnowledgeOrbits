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
import { notFound } from "next/navigation";

// Revalidate every hour
export const revalidate = 3600;

// Pre-render topics for stability during build
export async function generateStaticParams() {
  try {
    const topics = await topicsAPI.list({ page_size: 200 });
    return (topics || []).map((topic) => ({ id: topic.id }));
  } catch (error) {
    console.error(
      "BUILD WARNING: generateStaticParams for Topics failed (likely Render timeout). Skipping pre-build.",
      error,
    );
    return [];
  }
}

interface TopicPageProps {
  params: Promise<{ id: string }>;
}

export default async function TopicDetailPage({ params }: TopicPageProps) {
  const { id: topicId } = await params;

  try {
    // Fetch topic details and articles concurrently on the server
    const [topic, articlesData] = await Promise.all([
      topicsAPI.getById(topicId),
      articlesAPI.listByTopic(topicId),
    ]);

    if (!topic) {
      return notFound();
    }

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
              <div className="flex items-center gap-3 mb-3 text-sm font-medium text-gray-500 uppercase tracking-widest">
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
              <h1 className="text-4xl font-black text-gray-900 leading-tight">
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
            <p className="text-gray-600 text-lg mb-8 leading-relaxed max-w-4xl">
              {topic.description}
            </p>
          )}

          {topic.keywords && topic.keywords.length > 0 && (
            <div className="flex items-start gap-3 border-t pt-6 bg-gray-50/50 p-4 rounded-lg">
              <Hash className="h-5 w-5 mt-0.5 text-gray-400" />
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
            <h2 className="text-3xl font-black text-gray-800 font-heading">
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
            <div className="text-center py-20 bg-gray-50/50 rounded-xl border border-dashed border-gray-300">
              <div className="max-w-md mx-auto">
                <p className="text-gray-500 text-lg mb-6">
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
    console.warn("Error loading topic details in Server Component:", error instanceof Error ? error.message : String(error));
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center py-12 bg-red-50 text-red-600 rounded-lg border border-red-200">
          Error retrieving topic. It might not exist or the data service is
          down.
        </div>
      </div>
    );
  }
}
