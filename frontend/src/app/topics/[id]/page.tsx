/**
 * Topic detail page
 */

"use client";

import { useParams } from "next/navigation";
import { useTopic } from "@/lib/hooks/use-topics";
import { useArticlesByTopic } from "@/lib/hooks/use-article";
import ArticleCard from "@/components/articles/article-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, BookOpen, Layers, Hash } from "lucide-react";
import Link from "next/link";
import { Article } from "@/lib/types";

export default function TopicDetailPage() {
  const params = useParams();
  const topicId = params.id as string;

  // Fetch topic details
  const {
    data: topic,
    isLoading: isTopicLoading,
    error: topicError,
  } = useTopic(topicId);

  // Fetch related articles
  const { data: articlesData, isLoading: isArticlesLoading } =
    useArticlesByTopic(topicId);

  if (isTopicLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="h-8 w-32 mb-8" />
        <Skeleton className="h-12 w-96 mb-4" />
        <Skeleton className="h-24 w-full mb-8" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      </div>
    );
  }

  if (topicError || !topic) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center text-red-600">
          Topic not found or error loading topic.
        </div>
      </div>
    );
  }

  const articles = articlesData || [];

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
      <div className="mb-8 p-6 bg-white rounded-lg border shadow-sm">
        <div className="flex justify-between items-start gap-4 mb-4">
          <div>
            <div className="flex items-center gap-2 mb-2 text-sm text-gray-500">
              <span className="flex items-center gap-1">
                <BookOpen className="h-4 w-4" />
                {topic.subject_name}
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Layers className="h-4 w-4" />
                {topic.module_name}
              </span>
            </div>
            <h1 className="text-3xl font-bold text-gray-900">{topic.name}</h1>
          </div>
          <Badge
            variant={topic.topic_type === "syllabus" ? "default" : "secondary"}
            className="text-sm"
          >
            {topic.topic_type}
          </Badge>
        </div>

        {topic.description && (
          <p className="text-gray-600 mb-6 leading-relaxed">
            {topic.description}
          </p>
        )}

        {topic.keywords && topic.keywords.length > 0 && (
          <div className="flex items-start gap-2">
            <Hash className="h-4 w-4 mt-1 text-gray-400" />
            <div className="flex flex-wrap gap-2">
              {topic.keywords.map((kw, i) => (
                <Badge key={i} variant="outline" className="bg-gray-50">
                  {kw}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Articles Section */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-800">Study Materials</h2>
          {articles.length > 0 && (
            <span className="text-sm text-gray-500">
              {articles.length} article{articles.length !== 1 ? "s" : ""}{" "}
              available
            </span>
          )}
        </div>

        {isArticlesLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-64" />
            ))}
          </div>
        ) : articles.length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed">
            <p className="text-gray-600 mb-4">
              No articles generated for this topic yet.
            </p>
            <Link href={`/generate?topic=${topic.id}`}>
              <Button>Generate Article</Button>
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {articles.map((article: Article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
