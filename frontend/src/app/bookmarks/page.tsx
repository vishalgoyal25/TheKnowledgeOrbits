"use client";

import { useBookmarks } from "@/lib/hooks/use-bookmarks";
import BookmarkCard from "@/components/bookmarks/BookmarkCard";
import EmptyState from "@/components/notebook/EmptyState";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { Loader2, BookMarked, BookOpen } from "lucide-react";
import { useRouter } from "next/navigation";

export default function BookmarksPage() {
  const router = useRouter();
  // Only fetch 'article' bookmarks as requested
  const { data: bookmarks, isLoading, refetch } = useBookmarks("article");

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <BookMarked className="h-8 w-8 text-blue-600" />
              Bookmarked Articles
            </h1>
            <p className="text-gray-600 mt-1">
              Your curated collection of saved articles.
            </p>
          </div>
          <Link href="/articles">
            <Button className="gap-2">
              <BookOpen className="h-5 w-5" />
              Browse Articles
            </Button>
          </Link>
        </div>

        {/* Bookmarks List (Articles Only) */}
        {bookmarks && bookmarks.length > 0 ? (
          <div className="space-y-4">
            {bookmarks.map((bookmark) => (
              <BookmarkCard
                key={bookmark.id}
                bookmark={bookmark}
                onRemove={() => refetch()}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No bookmarked articles"
            description="Bookmark insightful articles from the library to save them here."
            actionLabel="Browse Articles"
            onAction={() => router.push("/articles")}
          />
        )}
      </div>
    </div>
  );
}
