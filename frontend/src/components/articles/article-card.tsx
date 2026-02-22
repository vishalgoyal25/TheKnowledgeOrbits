/**
 * Article preview card
 */

"use client";

import Link from "next/link";
import { Article } from "@/lib/types";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Clock, FileText, Folder, Star } from "lucide-react";
import {
  formatRelativeTime,
  getQualityColor,
  getReviewStatusColor,
} from "@/lib/utils";

interface ArticleCardProps {
  article: Article;
}

export default function ArticleCard({ article }: ArticleCardProps) {
  return (
    <Link href={`/articles/${article.id}`}>
      <Card className="h-full transition-all hover:shadow-lg hover:scale-[1.02]">
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-lg font-semibold line-clamp-2 flex-1">
              {article.title}
            </h3>
            <Badge
              variant="secondary"
              className={getReviewStatusColor(article.review_status)}
            >
              {article.review_status}
            </Badge>
          </div>

          {/* Topic */}
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Folder className="h-4 w-4" />
            <span>{article.topic.name}</span>
          </div>
        </CardHeader>

        <CardContent>
          {/* Summary */}
          <p className="text-sm text-gray-600 line-clamp-3">
            {article.summary}
          </p>
        </CardContent>

        <CardFooter className="flex items-center justify-between text-sm text-gray-500">
          {/* Metadata */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <FileText className="h-4 w-4" />
              <span>{article.word_count} words</span>
            </div>

            <div className="flex items-center gap-1">
              <Clock className="h-4 w-4" />
              <span>{article.read_time} min read</span>
            </div>

            <div className="flex items-center gap-1">
              <Star
                className={`h-4 w-4 ${getQualityColor(article.quality_score)}`}
              />
              <span className={getQualityColor(article.quality_score)}>
                {article.quality_score.toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Date */}
          <span>{formatRelativeTime(article.created_at)}</span>
        </CardFooter>
      </Card>
    </Link>
  );
}
