"use client";

import { useArticle } from "@/lib/hooks/use-article";
import ArticleReader from "@/components/articles/article-reader";
import SourceAttribution from "@/components/quiz/source-attribution";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Share2, BookmarkPlus, Loader2 } from "lucide-react";
import Link from "next/link";
import { Article, ArticleSourceMap } from "@/lib/types";
import ArticleSkeleton from "@/components/articles/article-skeleton";

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

  // Elite 5.1: High-fidelity loading state using shimmering silhouettes
  if (isArticleLoading) {
    return (
      <div className="container mx-auto px-4 py-8 animate-in fade-in duration-700">
        <div className="mb-4 flex gap-2 items-center justify-center p-3 text-blue-600 bg-blue-50/50 rounded-xl border border-blue-100/50 text-xs font-bold uppercase tracking-widest animate-pulse">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Synchronizing Secure Intelligence
        </div>
        <ArticleSkeleton />
      </div>
    );
  }

  // Silent Resilience 5.2: Minimalistic error handling that prioritizes the "Shimmer" over a loud Error Bar
  if (isArticleError || !articleData) {
    return (
      <div className="container mx-auto px-4 py-16 text-center animate-in fade-in slide-in-from-bottom-2">
        <div className="max-w-xl mx-auto p-12 bg-white rounded-3xl border border-gray-100 shadow-xl shadow-blue-500/5 items-center flex flex-col gap-6">
          <div className="h-16 w-16 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center rotate-3 scale-110">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-black text-gray-900 tracking-tight">
              Synchronization Delayed
            </h2>
            <p className="text-gray-500 font-medium max-w-sm mx-auto leading-relaxed">
              We're having trouble connecting to the intelligence engine. We'll
              keep trying in the background, or you can manually trigger a
              refresh.
            </p>
          </div>
          <div className="flex flex-col w-full gap-3 mt-4">
            <Button
              onClick={() => refetch()}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold h-12 rounded-xl shadow-lg shadow-blue-600/20"
            >
              Force Synchronize
            </Button>
            <Link
              href="/articles"
              className="text-xs text-gray-400 font-bold hover:text-blue-600 uppercase tracking-widest transition-colors"
            >
              Return to Catalog
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
        const sourceChunks = article?.source_chunks;
        if (!sourceChunks || sourceChunks.length === 0) return null;
        return (
          <div className="mt-8 max-w-3xl mx-auto">
            <SourceAttribution
              sources={(sourceChunks as unknown as ArticleSourceMap[])
                .filter((s) => s != null)
                .map((s: ArticleSourceMap) => ({
                  title:
                    s?.chunk_text?.slice?.(0, 80) ||
                    s?.chunk?.chunk_text?.slice?.(0, 80) ||
                    s?.chunk_contribution ||
                    "Secure Intelligence Source",
                  document_title:
                    s?.chapter_name ||
                    s?.chunk?.document_title ||
                    "Knowledge Module",
                  chunk_index: s?.sequence_order ?? s?.chunk?.chunk_index ?? 0,
                  relevance_score: s?.relevance_weight ?? 1,
                }))}
            />
          </div>
        );
      })()}
    </div>
  );
}
