'use client';

import { useState } from 'react';
import { useBookmarks } from '@/lib/hooks/useBookmarks';
import { Card } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import BookmarkCard from '@/components/bookmarks/BookmarkCard';
import EmptyState from '@/components/notebook/EmptyState';
import { Loader2, BookMarked } from 'lucide-react';

export default function BookmarksPage() {
  const [activeTab, setActiveTab] = useState<'all' | 'article' | 'quiz'>('all');
  const { data: bookmarks, isLoading, refetch } = useBookmarks(activeTab === 'all' ? undefined : activeTab);

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
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            <BookMarked className="h-8 w-8 text-blue-600" />
            Bookmarks
          </h1>
          <p className="text-gray-600 mt-1">Your saved articles and quizzes</p>
        </div>

        {/* Tabs */}
        <Card className="mb-6">
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="all">All ({bookmarks?.length || 0})</TabsTrigger>
              <TabsTrigger value="article">
                Articles ({bookmarks?.filter(b => b.content_type === 'article').length || 0})
              </TabsTrigger>
              <TabsTrigger value="quiz">
                Quizzes ({bookmarks?.filter(b => b.content_type === 'quiz').length || 0})
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </Card>

        {/* Bookmarks List */}
        {bookmarks && bookmarks.length > 0 ? (
          <div className="space-y-4">
            {bookmarks.map(bookmark => (
              <BookmarkCard
                key={bookmark.id}
                bookmark={bookmark}
                onRemove={() => refetch()}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No bookmarks yet"
            description="Bookmark articles and quizzes to access them quickly"
            actionLabel="Browse Articles"
            onAction={() => window.location.href = '/articles'}
          />
        )}
      </div>
    </div>
  );
}
