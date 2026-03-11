"use client";

import { useArticle } from "@/lib/hooks/use-article";
import ArticleReader from "@/components/articles/article-reader";
import SourceAttribution from "@/components/quiz/source-attribution";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Share2, BookmarkPlus, Loader2 } from "lucide-react";
import Link from "next/link";
import { Article, ArticleSourceMap } from "@/lib/types";

export default function PrivateArticleFallback({
  articleId,
}: {
  articleId: string;
}) {
  const {
    data: articleData,
    isLoading: isArticleLoading,
    isError: isArticleError,
    refetch,
  } = useArticle(articleId);

  if (isArticleLoading) {
    return (
      <div className="container mx-auto px-4 py-32 text-center flex flex-col items-center justify-center">
        <Loader2 className="h-10 w-10 animate-spin text-blue-500 mb-4" />
        <h2 className="text-xl font-bold text-gray-900 mb-2">
          Decrypting Secure Asset
        </h2>
        <p className="text-gray-500 font-medium">
          Authorizing and fetching your privately generated intelligence...
        </p>
      </div>
    );
  }

  if (isArticleError || !articleData) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <div className="max-w-md mx-auto p-8 bg-amber-50 rounded-2xl border border-amber-100 shadow-sm">
          <div className="h-12 w-12 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
          <h2 className="text-xl font-bold text-amber-900 mb-2">
            Asset Unavailable
          </h2>
          <p className="text-amber-700 mb-6 font-medium">
            We couldn't retrieve this article. It might be generating, or you
            may need to check your connection.
          </p>
          <div className="flex flex-col gap-3">
            <Button
              onClick={() => refetch()}
              className="w-full bg-amber-600 hover:bg-amber-700"
            >
              Manual Retry
            </Button>
            <Link
              href="/articles"
              className="text-sm text-amber-600 font-bold hover:underline"
            >
              Browse other articles
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const article = articleData as Article;

  return (
    <div className="container mx-auto px-4 py-8 animate-in fade-in duration-500">
      {/* Back button */}
      <div className="mb-8 flex items-center justify-between">
        <Link href="/articles">
          <Button variant="ghost" className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Articles
          </Button>
        </Link>
        <div className="px-3 py-1 bg-amber-100 text-amber-800 text-xs font-bold rounded-full uppercase tracking-wider">
          Private Asset
        </div>
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

      {/* Article Reader */}
      <ArticleReader article={article} />

      {/* Source Attribution */}
      {(() => {
        const sourceChunks = article.source_chunks;
        if (!sourceChunks || sourceChunks.length === 0) return null;
        return (
          <div className="mt-8 max-w-3xl mx-auto">
            <SourceAttribution
              sources={sourceChunks.map((s: ArticleSourceMap) => ({
                title:
                  s.chunk_text?.slice(0, 80) ||
                  s.chunk_contribution ||
                  "Source",
                document_title: s.chapter_name || "Knowledge Base",
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
