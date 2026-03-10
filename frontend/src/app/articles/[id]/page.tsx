/**
 * Article detail page (Server Component with ISR)
 */

import { articlesAPI } from "@/lib/api/articles";
import { Article } from "@/lib/types";
import ArticleReader from "@/components/articles/article-reader";
import SourceAttribution from "@/components/quiz/source-attribution";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Share2, BookmarkPlus, Loader2 } from "lucide-react";
import Link from "next/link";
import apiClient from "@/lib/api/client";

// Revalidate every hour
export const revalidate = 3600;

// Pre-render the Latest 100 articles for stability
export async function generateStaticParams() {
  try {
    const response = await articlesAPI.list({ limit: 100 });
    return (response.results || []).map((article: Article) => ({
      id: article.id,
    }));
  } catch (error) {
    console.error("BUILD WARNING: generateStaticParams for Articles failed (likely Render timeout). skipping pre-build.", error);
    return [];
  }
}

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ type?: string; chunk?: string }>;
}

/**
 * Fetch a document and its chunks to mimic an Article on the server
 */
async function fetchDocumentAsArticle(documentId: string, chunkIndexStr?: string): Promise<Article | null> {
  try {
    const chunkIndex = chunkIndexStr ? parseInt(chunkIndexStr) : 0;
    
    // 1. Fetch Document Metadata
    const docRes = await apiClient.get(`/content/documents/${documentId}/`);
    const doc = docRes.data;

    // 2. Fetch Chunks
    const chunksRes = await apiClient.get(`/content/chunks/`, {
      params: {
        document: documentId,
        limit: 20,
        start_index: Math.max(0, chunkIndex - 1),
        include_content: "true",
      },
    });

    const chunks = chunksRes.data.results || [];
    chunks.sort((a: { chunk_index: number }, b: { chunk_index: number }) => a.chunk_index - b.chunk_index);
    const content = chunks.map((c: { chunk_text: string }) => c.chunk_text).join("\n\n");

    return {
      id: doc.id,
      title: doc.title,
      content: content || "No content available for this section.",
      summary: doc.description || "Document content",
      topic: null,
      word_count: content.split(/\s+/).length,
      read_time: Math.ceil(content.split(/\s+/).length / 200).toString(),
      generation_type: "human_curated",
      quality_score: 100,
      review_status: "approved",
      is_published: true,
      published_at: doc.created_at,
      created_at: doc.created_at,
      updated_at: doc.created_at,
      source_chunks: [],
      source_chunk_count: chunks.length,
      static_chunk_count: chunks.length,
      ca_chunk_count: 0,
      slug: doc.title.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
    } as unknown as Article;
  } catch (error) {
    console.error("Error fetching document as article on server:", error);
    return null;
  }
}

export default async function ArticleDetailPage({ params, searchParams }: PageProps) {
  const { id: articleId } = await params;
  const { type, chunk } = await searchParams;

  let article: Article | null = null;

  try {
    if (type === "document") {
      article = await fetchDocumentAsArticle(articleId, chunk);
    } else {
      article = await articlesAPI.getById(articleId);
    }

    if (!article) {
      // If article is missing, it's likely a sync issue in the distributed cloud. 
      // Throw to show the "Service is Busy" retry screen instead of a hard 404.
      throw new Error("Content synchronization pending");
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

        {/* Actions (Client components will hydrate over these) */}
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

        {/* Article Reader (Client component handles hydration of interactive features) */}
        <ArticleReader article={article} />

        {/* Source Attribution (Server side rendering for SEO and speed) */}
        {(() => {
          const sourceChunks = article.source_chunks;
          if (!sourceChunks || sourceChunks.length === 0) return null;
          return (
            <div className="mt-8 max-w-3xl mx-auto">
              <SourceAttribution
                sources={sourceChunks.map((s) => ({
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
  } catch (error) {
    console.error("Error loading article details in Server Component:", error);
    
    // Check if it's a 503 or network error
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <div className="max-w-md mx-auto p-8 bg-amber-50 rounded-2xl border border-amber-100 shadow-sm">
          <div className="h-12 w-12 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
          <h2 className="text-xl font-bold text-amber-900 mb-2">Service is Busy</h2>
          <p className="text-amber-700 mb-6">
            The Knowledge Library is currently under heavy load. We are retrying to fetch this article for you...
          </p>
          <div className="flex flex-col gap-3">
             <Button 
              onClick={() => typeof window !== 'undefined' && window.location.reload()}
              className="w-full bg-amber-600 hover:bg-amber-700"
            >
              Manual Retry
            </Button>
            <Link href="/articles" className="text-sm text-amber-600 hover:underline">
              Browse other articles
            </Link>
          </div>
        </div>
        <script dangerouslySetInnerHTML={{ 
          __html: `setTimeout(() => window.location.reload(), 5000)` 
        }} />
      </div>
    );
  }
}
