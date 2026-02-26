"use client";

import { useBookmarkToggle } from "@/lib/hooks/use-bookmark-toggle";
import { Button } from "@/components/ui/button";
import { Bookmark, BookmarkCheck } from "lucide-react";

interface Props {
  contentType: "article" | "quiz";
  contentId: string;
  title: string;
}

export default function BookmarkButton({
  contentType,
  contentId,
  title: _title,
}: Props) {
  const { isBookmarked, toggle, isLoading } = useBookmarkToggle(
    contentType,
    contentId,
  );

  return (
    <Button
      variant={isBookmarked ? "default" : "outline"}
      size="sm"
      onClick={toggle}
      disabled={isLoading}
      className="flex items-center gap-2"
    >
      {isBookmarked ? (
        <>
          <BookmarkCheck className="h-4 w-4" />
          Bookmarked
        </>
      ) : (
        <>
          <Bookmark className="h-4 w-4" />
          Bookmark
        </>
      )}
    </Button>
  );
}
