/**
 * Topic preview card
 */

"use client";

import Link from "next/link";
import { Topic } from "@/lib/types";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FileText, Layers, TrendingUp } from "lucide-react";
import { getDifficultyColor } from "@/lib/utils";

interface TopicCardProps {
  topic: Topic;
  articleCount?: number;
}

export default function TopicCard({ topic, articleCount = 0 }: TopicCardProps) {
  return (
    <Link href={`/topics/${topic.id}/articles`}>
      <Card className="h-full transition-all hover:shadow-lg hover:scale-[1.02]">
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-lg line-clamp-2 flex-1">
              {topic.name}
            </CardTitle>

            {topic.difficulty_level && (
              <Badge className={getDifficultyColor(topic.difficulty_level)}>
                {topic.difficulty_level}
              </Badge>
            )}
          </div>
        </CardHeader>

        <CardContent>
          <p className="text-sm text-gray-600 line-clamp-3 mb-4">
            {topic.description}
          </p>

          {/* Keywords */}
          {topic.keywords && topic.keywords.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {topic.keywords.slice(0, 3).map((keyword, idx) => (
                <Badge key={idx} variant="outline" className="text-xs">
                  {keyword}
                </Badge>
              ))}
              {topic.keywords.length > 3 && (
                <Badge variant="outline" className="text-xs">
                  +{topic.keywords.length - 3}
                </Badge>
              )}
            </div>
          )}
        </CardContent>

        <CardFooter className="text-sm text-gray-600">
          <div className="flex items-center gap-4 w-full">
            <div className="flex items-center gap-1">
              <FileText className="h-4 w-4" />
              <span>{articleCount} articles</span>
            </div>

            <div className="flex items-center gap-1">
              <Layers className="h-4 w-4" />
              <span>{topic.module_name}</span>
            </div>
          </div>
        </CardFooter>
      </Card>
    </Link>
  );
}
