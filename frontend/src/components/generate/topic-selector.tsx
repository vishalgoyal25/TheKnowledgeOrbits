/**
 * Topic selection component
 */

"use client";

import { useState } from "react";
import { useTopics } from "@/lib/hooks/use-topics";
import { Topic } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Search, Folder } from "lucide-react";
import { getDifficultyColor } from "@/lib/utils";

interface TopicSelectorProps {
  onSelectTopic: (topic: Topic) => void;
  selectedTopicId?: string;
}

export default function TopicSelector({
  onSelectTopic,
  selectedTopicId,
}: TopicSelectorProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const { data: topicsData, isLoading } = useTopics();

  const topics = topicsData?.results || [];

  // Filter topics
  const filteredTopics = topics.filter(
    (topic) =>
      topic.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      topic.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      topic.keywords?.some((k) =>
        k.toLowerCase().includes(searchTerm.toLowerCase()),
      ),
  );

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <Input
          placeholder="Search topics..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Results count */}
      <p className="text-sm text-gray-600">
        {filteredTopics.length} topics available
      </p>

      {/* Topic List */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {filteredTopics.map((topic) => (
          <Card
            key={topic.id}
            className={`cursor-pointer transition-all hover:shadow-md ${
              selectedTopicId === topic.id ? "ring-2 ring-blue-500" : ""
            }`}
            onClick={() => onSelectTopic(topic)}
          >
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <h4 className="font-semibold mb-1">{topic.name}</h4>
                  <p className="text-sm text-gray-600 line-clamp-1 mb-2">
                    {topic.description}
                  </p>

                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <Folder className="h-3 w-3" />
                    <span>{topic.module_name}</span>
                    <span>•</span>
                    <span>{topic.subject_name}</span>
                  </div>
                </div>

                {topic.difficulty_level && (
                  <Badge className={getDifficultyColor(topic.difficulty_level)}>
                    {topic.difficulty_level}
                  </Badge>
                )}
              </div>
            </CardContent>
          </Card>
        ))}

        {filteredTopics.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No topics found matching &quot;{searchTerm}&quot;
          </div>
        )}
      </div>
    </div>
  );
}
