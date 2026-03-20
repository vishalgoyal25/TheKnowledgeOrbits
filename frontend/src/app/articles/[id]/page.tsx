/**
 * Article detail page (Server Component with ISR)
 */

import { articlesAPI } from "@/lib/api/articles";
import { Article } from "@/lib/types";
import ArticleReader from "@/components/articles/article-reader";
import SourceAttribution from "@/components/quiz/source-attribution";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Share2, BookmarkPlus } from "lucide-react";
import Link from "next/link";
import apiClient from "@/lib/api/client";
import PrivateArticleFallback from "./private-article-fallback";

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
    console.error(
      "BUILD WARNING: generateStaticParams for Articles failed (likely Render timeout). skipping pre-build.",
      error,
    );
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
async function fetchDocumentAsArticle(
  documentId: string,
  chunkIndexStr?: string,
): Promise<Article | null> {
  try {
    const chunkIndex = chunkIndexStr ? parseInt(chunkIndexStr) : 0;

    // Fetch Document Metadata and Chunks in parallel
    const [docRes, chunksRes] = await Promise.all([
      apiClient.get(`/content/documents/${documentId}/`),
      apiClient.get(`/content/chunks/`, {
        params: {
          document: documentId,
          limit: 20,
          start_index: Math.max(0, chunkIndex - 1),
          include_content: "true",
        },
      }),
    ]);
    const doc = docRes.data;

    const chunks = chunksRes.data.results || [];
    chunks.sort(
      (a: { chunk_index: number }, b: { chunk_index: number }) =>
        a.chunk_index - b.chunk_index,
    );
    const content = chunks
      .map((c: { chunk_text: string }) => c.chunk_text)
      .join("\n\n");

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

export default async function ArticleDetailPage({
  params,
  searchParams,
}: PageProps) {
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
                sources={(sourceChunks || []).map((s) => ({
                  title:
                    s.chunk_text?.slice(0, 80) ||
                    s.chunk?.chunk_text?.slice(0, 80) ||
                    s.chunk_contribution ||
                    "Contextual Source",
                  document_title:
                    s.chapter_name ||
                    s.chunk?.document_title ||
                    "Knowledge Cluster",
                  chunk_index: s.sequence_order ?? s.chunk?.chunk_index ?? 0,
                  relevance_score: s.relevance_weight,
                }))}
              />
            </div>
          );
        })()}
      </div>
    );
  } catch (error) {
    console.warn(
      "ISR Fetch Failed (Likely a Private Article or 404). Falling back to Secure Client Component:",
      error,
    );

    // This is the true power of React Server Components:
    // If the Server (unauthenticated) cannot fetch it, maybe the Client (authenticated) can!
    return <PrivateArticleFallback articleId={articleId} />;
  }
}
