/**
 * Article sources page
 */

"use client";

import { useParams } from "next/navigation";
import { useArticle, useArticleSources } from "@/lib/hooks/use-article";
import SourceViewer from "@/components/articles/source-viewer";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, FileText } from "lucide-react";
import Link from "next/link";

export default function ArticleSourcesPage() {
  const params = useParams();
  const articleId = params.id as string;

  const { data: article } = useArticle(articleId);
  const { data: sourcesData, isLoading, error } = useArticleSources(articleId);

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="h-12 w-32 mb-8" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !sourcesData) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center text-red-600">Error loading sources.</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Back button */}
      <div className="mb-8">
        <Link href={`/articles/${articleId}`}>
          <Button variant="ghost" className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Article
          </Button>
        </Link>
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Source Materials</h1>
        <p className="text-gray-600">{article?.title || "Article"}</p>

        <div className="mt-4 flex items-center gap-2 text-sm text-gray-600">
          <FileText className="h-4 w-4" />
          <span>{sourcesData.total_sources} source materials used</span>
        </div>
      </div>

      {/* Sources */}
      <SourceViewer sources={sourcesData.sources} />
    </div>
  );
}
