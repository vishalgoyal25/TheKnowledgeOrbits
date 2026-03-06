/**
 * CA Article Card Component
 */

"use client";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { currentAffairsAPI } from "@/lib/api/current-affairs";
import { CAArticle } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";
import { useQueryClient } from "@tanstack/react-query";
import { Calendar, ExternalLink, FileText, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";

interface CAArticleCardProps {
  article: CAArticle;
}

export default function CAArticleCard({ article }: CAArticleCardProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800";
      case "processing":
        return "bg-blue-100 text-blue-800";
      case "pending":
        return "bg-yellow-100 text-yellow-800";
      case "failed":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const router = useRouter();
  const queryClient = useQueryClient();

  const handlePrefetch = () => {
    // Prefetch CA article detail on hover so click feels instant
    queryClient.prefetchQuery({
      queryKey: ["ca-article", article.id],
      queryFn: () => currentAffairsAPI.getArticle(article.id),
      staleTime: 10 * 60 * 1000,
    });
  };

  return (
    <Card
      className="h-full transition-all hover:shadow-lg cursor-pointer"
      onClick={() => router.push(`/current-affairs/${article.id}`)}
      onMouseEnter={handlePrefetch}
    >
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-lg line-clamp-2 flex-1">
            {article.title}
          </CardTitle>

          <Badge
            variant="secondary"
            className={getStatusColor(article.processing_status)}
          >
            {article.processing_status}
          </Badge>
        </div>

        <div className="flex items-center gap-2 text-sm text-gray-600">
          <Sparkles className="h-4 w-4 text-blue-500" />
          <span>{article.source_name}</span>
        </div>
      </CardHeader>

      <CardContent>
        <p className="text-sm text-gray-600 line-clamp-3">
          {article.summary ||
            (article.content ? article.content.substring(0, 150) + "..." : "")}
        </p>

        {/* Categories */}
        {article.categories && article.categories.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {article.categories.slice(0, 3).map((category, idx) => (
              <Badge key={idx} variant="outline" className="text-xs">
                {category}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>

      <CardFooter className="flex items-center justify-between text-sm text-gray-500">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1">
            <Calendar className="h-4 w-4" />
            <span>{formatRelativeTime(article.published_at)}</span>
          </div>

          {article.processing_status === "completed" && (
            <div className="flex items-center gap-1">
              <FileText className="h-4 w-4" />
              <span>{article.chunk_count} chunks</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
          >
            <Badge
              variant="outline"
              className="cursor-pointer hover:bg-gray-100 gap-1"
            >
              Source <ExternalLink className="h-3 w-3" />
            </Badge>
          </a>
        </div>
      </CardFooter>
    </Card>
  );
}
