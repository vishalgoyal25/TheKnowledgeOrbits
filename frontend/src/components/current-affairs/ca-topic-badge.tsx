/**
 * CA Topic Badge - Shows CA count for a topic
 */

"use client";

import { Badge } from "@/components/ui/badge";
import { Newspaper } from "lucide-react";

interface CATopicBadgeProps {
  count: number;
}

export default function CATopicBadge({ count }: CATopicBadgeProps) {
  if (count === 0) return null;

  return (
    <Badge variant="outline" className="bg-blue-50 text-blue-700 gap-1">
      <Newspaper className="h-3 w-3" />
      {count} CA
    </Badge>
  );
}
