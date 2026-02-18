/**
 * Article detail page
 */

'use client';

import { useParams } from 'next/navigation';
import { useArticle } from '@/lib/hooks/use-article';
import ArticleReader from '@/components/articles/article-reader';
import SourceAttribution from '@/components/quiz/source-attribution';
import ErrorMessage from '@/components/shared/error-message';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, Share2, BookmarkPlus } from 'lucide-react';
import Link from 'next/link';

export default function ArticleDetailPage() {
  const params = useParams();
  const articleId = params.id as string;

  const { data: article, isLoading, error } = useArticle(articleId);

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="h-12 w-32 mb-8" />
        <Skeleton className="h-16 w-full mb-4" />
        <Skeleton className="h-8 w-3/4 mb-8" />
        <div className="space-y-4">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
        </div>
      </div>
    );
  }

  if (error || !article) {
    return (
      <div className="container mx-auto px-4 py-8">
        <ErrorMessage
          title="Article not found"
          message="This article may have been removed or the link is incorrect."
          onRetry={() => window.location.reload()}
        />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Back button */}
      <div className="mb-8">
        <Link href="/articles">
          <Button variant="ghost" className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Articles
          </Button>
        </Link>
      </div>

      {/* Actions */}
      <div className="mb-8 flex gap-2 justify-end">
        <Button variant="outline" size="sm" className="gap-2">
          <BookmarkPlus className="h-4 w-4" />
          Save
        </Button>
        <Button variant="outline" size="sm" className="gap-2">
          <Share2 className="h-4 w-4" />
          Share
        </Button>
      </div>

      {/* Article */}
      <ArticleReader article={article} />

      {/* Source Attribution */}
      {(() => {
        const sourceChunks = article.source_chunks;
        if (!sourceChunks || sourceChunks.length === 0) return null;
        return (
          <div className="mt-8 max-w-3xl mx-auto">
            <SourceAttribution
              sources={sourceChunks.map((s) => ({
                title: s.chunk?.chunk_text?.slice(0, 80) || s.chunk_contribution || 'Source',
                document_title: s.chunk?.document_title || 'Knowledge Base',
                chunk_index: s.sequence_order ?? 0,
                relevance_score: s.relevance_weight,
              }))}
            />
          </div>
        );
      })()}



    </div>
  );
}
