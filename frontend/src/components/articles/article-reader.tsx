/**
 * Article reader (Server-side compatible)
 * Combines server-rendered header and content with client-side progress tracking.
 */

import { Article } from "@/lib/types";
import ArticleHeader from "./article-header";
import ArticleContent from "./article-content";
import ReadingProgressTracker from "./reading-progress-tracker";
import { Badge } from "@/components/ui/badge";
import { Newspaper } from "lucide-react";

interface ArticleReaderProps {
  article: Article;
}

export default function ArticleReader({ article }: ArticleReaderProps) {
  // Source breakdown counts
  const sourceChunksArr = article?.source_chunks || [];
  const totalSources =
    sourceChunksArr.length || article?.source_chunk_count || 0;

  const staticSources =
    sourceChunksArr.filter((s) => s?.chunk?.source_type === "static").length ||
    article?.static_chunk_count ||
    0;

  const caSources =
    sourceChunksArr.filter((s) => s?.chunk?.source_type === "dynamic").length ||
    article?.ca_chunk_count ||
    article?.generation_metadata?.ca_chunks_used ||
    0;

  return (
    <div className="min-h-screen bg-white">
      {/* Fixed Reading Progress Tracker (Client-side) */}
      <ReadingProgressTracker articleId={article.id} />

      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Article Header (title, topic, metadata) */}
        <ArticleHeader article={article} />

        {/* Article Content (Server rendered) */}
        <ArticleContent content={article.content} />

        {/* Footer with source attribution & CA info */}
        <footer className="mt-12 pt-8 border-t">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 text-sm text-gray-600">
            <div>
              <p className="font-medium">
                Knowledge Orchestration by TheKnowledgeOrbits
              </p>
              <p className="flex items-center gap-2 mt-1">
                Refined from {totalSources} foundational source
                {totalSources !== 1 ? "s" : ""}
                {staticSources > 0 && caSources > 0 && (
                  <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full font-bold">
                    {staticSources} TEXTBOOKS + {caSources} CURRENT AFFAIRS
                  </span>
                )}
              </p>
              <p className="text-xs mt-2 text-gray-400">
                Published on{" "}
                {article.created_at && !isNaN(new Date(article.created_at).getTime())
                  ? new Date(article.created_at).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })
                  : "Recently"}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className="px-3 py-1 bg-gray-50 border-gray-200 text-gray-700"
              >
                {(article?.generation_type || "ai_generated").replace("_", " ")}
              </Badge>

              {caSources > 0 && (
                <Badge className="bg-blue-600 text-white gap-1.5 px-3 py-1 border-none font-bold">
                  <Newspaper className="h-3.5 w-3.5" />
                  DYNAMIC CA
                </Badge>
              )}
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
