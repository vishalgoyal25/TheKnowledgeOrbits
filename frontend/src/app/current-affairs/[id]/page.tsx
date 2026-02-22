/**
 * CA Article Detail Page
 */

"use client";

import { useParams } from "next/navigation";
import { useCAArticle } from "@/lib/hooks/use-current-affairs";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  ArrowLeft,
  ExternalLink,
  Calendar,
  User,
  FileText,
} from "lucide-react";
import { formatDate } from "@/lib/utils";
import Link from "next/link";

export default function CAArticleDetailPage() {
  const params = useParams();
  const articleId = params.id as string;

  const { data: article, isLoading } = useCAArticle(articleId);

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="h-8 w-32 mb-8" />
        <Skeleton className="h-12 w-full mb-4" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!article) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center">
          <p className="text-gray-600">Article not found</p>
          <Link href="/current-affairs">
            <Button variant="outline" className="mt-4">
              Back to Current Affairs
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      {/* Back button */}
      <Link href="/current-affairs">
        <Button variant="ghost" className="mb-6 gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Current Affairs
        </Button>
      </Link>

      {/* Article Header */}
      <div className="mb-8">
        <div className="flex items-start justify-between gap-4 mb-4">
          <h1 className="text-4xl font-bold">{article.title}</h1>

          <Badge
            className={
              article.processing_status === "completed"
                ? "bg-green-100 text-green-800"
                : article.processing_status === "processing"
                  ? "bg-blue-100 text-blue-800"
                  : article.processing_status === "pending"
                    ? "bg-yellow-100 text-yellow-800"
                    : "bg-red-100 text-red-800"
            }
          >
            {article.processing_status}
          </Badge>
        </div>

        {/* Metadata */}
        <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600 mb-4">
          <div className="flex items-center gap-1">
            <Calendar className="h-4 w-4" />
            <span>{formatDate(article.published_at)}</span>
          </div>

          {article.author && (
            <div className="flex items-center gap-1">
              <User className="h-4 w-4" />
              <span>{article.author}</span>
            </div>
          )}

          <div className="flex items-center gap-1">
            <FileText className="h-4 w-4" />
            <span>{article.word_count} words</span>
          </div>

          {article.chunk_count > 0 && (
            <Badge variant="outline">
              {article.chunk_count} chunks processed
            </Badge>
          )}
        </div>

        {/* Source */}
        <div className="flex items-center justify-between">
          <Badge variant="secondary">{article.source_name}</Badge>

          <a href={article.url} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm" className="gap-2">
              Original Source <ExternalLink className="h-4 w-4" />
            </Button>
          </a>
        </div>
      </div>

      {/* Categories */}
      {article.categories && article.categories.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          {article.categories.map((category, idx) => (
            <Badge key={idx} variant="outline">
              {category}
            </Badge>
          ))}
        </div>
      )}

      {/* Summary */}
      {article.summary && (
        <Card className="mb-6 bg-blue-50">
          <CardContent className="pt-6">
            <h2 className="font-semibold mb-2">Summary</h2>
            <p className="text-gray-700">{article.summary}</p>
          </CardContent>
        </Card>
      )}

      {/* Content */}
      <Card>
        <CardContent className="pt-6">
          <div className="prose max-w-none">
            <div className="whitespace-pre-wrap text-gray-700 leading-relaxed">
              {article.content}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
