/**
 * CA Chunk Card Component
 */

"use client";

import { CAChunk } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Calendar, Link2, Sparkles } from "lucide-react";
import { formatDate } from "@/lib/utils";

interface CAChunkCardProps {
  chunk: CAChunk;
  showArticleTitle?: boolean;
}

export default function CAChunkCard({
  chunk,
  showArticleTitle = true,
}: CAChunkCardProps) {
  const getQualityColor = (flag: string) => {
    switch (flag) {
      case "high":
        return "bg-green-100 text-green-800";
      case "medium":
        return "bg-blue-100 text-blue-800";
      case "low":
        return "bg-yellow-100 text-yellow-800";
      case "needs_review":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <Card className={chunk.is_expired ? "opacity-50" : ""}>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          {showArticleTitle && (
            <CardTitle className="text-base line-clamp-2 flex-1">
              {chunk.article_title}
            </CardTitle>
          )}

          <div className="flex items-center gap-2">
            <Badge
              variant="secondary"
              className={getQualityColor(chunk.quality_flag)}
            >
              {chunk.quality_flag}
            </Badge>

            {chunk.is_expired && (
              <Badge variant="outline" className="bg-gray-100">
                Expired
              </Badge>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs text-gray-600">
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            <span>{formatDate(chunk.published_at)}</span>
          </div>

          {chunk.topic_count > 0 && (
            <div className="flex items-center gap-1">
              <Link2 className="h-3 w-3" />
              <span>{chunk.topic_count} topics</span>
            </div>
          )}

          <div className="flex items-center gap-1">
            <Sparkles className="h-3 w-3" />
            <span>Chunk {chunk.chunk_index}</span>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
          {chunk.chunk_text}
        </p>

        <div className="mt-3 text-xs text-gray-500">
          Confidence: {(chunk.confidence_score * 100).toFixed(0)}%
        </div>
      </CardContent>
    </Card>
  );
}
