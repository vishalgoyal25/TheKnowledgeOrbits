/**
 * Article detail page
 */

'use client';

import { useParams } from 'next/navigation';
import { useArticle } from '@/lib/hooks/use-articles';
import ArticleReader from '@/components/articles/article-reader';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, Share2, BookmarkPlus, ExternalLink } from 'lucide-react';
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
        <div className="text-center text-red-600">
          Article not found or error loading article.
        </div>
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
        
        <Link href={`/articles/${article.id}/sources`}>
          <Button variant="outline" size="sm" className="gap-2">
            <ExternalLink className="h-4 w-4" />
            View Sources
          </Button>
        </Link>
      </div>
      
      {/* Article */}
      <ArticleReader article={article} />
    </div>
  );
}
