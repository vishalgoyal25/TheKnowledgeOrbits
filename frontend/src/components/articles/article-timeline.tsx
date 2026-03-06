"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Article } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { BookOpen, Calendar } from "lucide-react";
import Link from "next/link";

interface ArticleTimelineProps {
  articles: Article[];
}

export default function ArticleTimeline({ articles }: ArticleTimelineProps) {
  // Group by date
  const groupedByDate = articles.reduce(
    (acc, article) => {
      const date = new Date(article.created_at).toDateString();
      if (!acc[date]) {
        acc[date] = [];
      }
      acc[date].push(article);
      return acc;
    },
    {} as Record<string, Article[]>,
  );

  return (
    <div className="space-y-8">
      {Object.entries(groupedByDate).map(([date, dayArticles]) => (
        <div key={date} className="relative">
          {/* Date Header */}
          <div className="sticky top-20 z-10 bg-white/95 backdrop-blur py-2 mb-4 border-b">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-blue-600" />
              <h3 className="font-semibold text-gray-900">
                {formatDate(dayArticles[0].created_at)}
              </h3>
              <Badge variant="secondary">{dayArticles.length} articles</Badge>
            </div>
          </div>

          {/* Articles for this day */}
          <div className="space-y-3 ml-6 border-l-2 border-blue-200 pl-4">
            {dayArticles.map((article) => (
              <Card
                key={article.id}
                className="relative hover:shadow-md transition-shadow"
              >
                {/* Timeline dot */}
                <div className="absolute -left-[29px] top-6 w-3 h-3 bg-blue-500 rounded-full border-2 border-white" />

                <CardContent className="pt-4">
                  <div className="flex items-start justify-between gap-2 mb-2 group">
                    <Link href={`/articles/${article.id}`} className="flex-1">
                      <h4 className="font-semibold group-hover:text-blue-600 transition-colors line-clamp-2 text-lg after:absolute after:inset-0">
                        {article.title}
                      </h4>
                    </Link>

                    {article.review_status && (
                      <Badge
                        variant={
                          article.review_status === "approved"
                            ? "default"
                            : "secondary"
                        }
                        className="flex-shrink-0 relative z-10 bg-white"
                      >
                        {article.review_status}
                      </Badge>
                    )}
                  </div>

                  <p className="text-sm text-gray-600 line-clamp-2 mb-3">
                    {article.summary ||
                      (article.content
                        ? article.content.substring(0, 150) + "..."
                        : "No summary available.")}
                  </p>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <BookOpen className="h-3 w-3" />
                      <span>{article.topic?.name || "Uncategorized"}</span>
                      <span>•</span>
                      <span>{article.read_time} min read</span>
                    </div>

                    <div className="text-xs text-gray-500 flex items-center gap-1">
                      {article.word_count} words
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
