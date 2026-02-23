"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useNotebook } from "@/lib/hooks/use-notebook";
import { useMyAttempts } from "@/lib/hooks/use-quiz";
import { useBookmarks } from "@/lib/hooks/use-bookmarks";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ArticleCard from "@/components/notebook/ArticleCard";
import AttemptCard from "@/components/quiz/attempt-card";
import BookmarkCard from "@/components/bookmarks/BookmarkCard";
import EmptyState from "@/components/notebook/EmptyState";
import {
  PlusCircle,
  Search,
  Loader2,
  BookOpen,
  FileQuestion,
  Bookmark,
} from "lucide-react";

/**
 * NotebookPage - The primary personal study hub for the user.
 * 
 * Provides a unified interface to access:
 * 1. AI-Generated Articles (Knowledge Orbits)
 * 2. Recent Quiz Attempts & Performance
 * 3. Saved Bookmarks & Notes
 * 
 * Features integrated search filtering across all tabs and fast switching
 * between content types via a Tabbed UI.
 */
export default function NotebookPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("articles"); // articles | quizzes | bookmarks
  const [searchQuery, setSearchQuery] = useState("");

  // 1. Articles Data
  const {
    data: articles,
    isLoading: articlesLoading,
    refetch: refetchArticles,
  } = useNotebook();

  // 2. Quizzes Data
  // Enable fetching even if not active tab? Or fetch always for fast switching?
  // Hooks usually cache, so fetching all is fine.
  const { data: attempts, isLoading: quizzesLoading } = useMyAttempts();

  // 3. Bookmarks Data
  const {
    data: bookmarks,
    isLoading: bookmarksLoading,
    refetch: refetchBookmarks,
  } = useBookmarks(undefined); // undefined for 'all'

  // Filtering Logic
  const filteredArticles = articles?.filter(
    (a) =>
      a.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.topic.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredAttempts = attempts?.filter(
    (a) =>
      a.quiz.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.quiz.topic.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredBookmarks = bookmarks?.filter((b) => {
    // Safely extract title from dynamic content structure
    const content = b.content as Record<string, any>;
    const title = content?.title || b.notes || "Untitled Bookmark";
    return title.toLowerCase().includes(searchQuery.toLowerCase());
  });

  // Consolidated Loading (only initial load)
  const isLoading = articlesLoading || quizzesLoading || bookmarksLoading;

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
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">My Notebook</h1>
            <p className="text-gray-600 mt-1">
              Your entire collection of articles, quizzes, and bookmarks.
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              onClick={() => router.push("/assessment")}
              variant="outline"
              className="flex items-center gap-2 border-blue-200 text-blue-700 hover:bg-blue-50"
            >
              <FileQuestion className="h-5 w-5" />
              Take Quiz
            </Button>
            <Button
              onClick={() => router.push("/generate")}
              className="flex items-center gap-2"
            >
              <PlusCircle className="h-5 w-5" />
              New Article
            </Button>
          </div>
        </div>

        {/* Search Bar */}
        <Card className="p-4 mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <Input
              type="text"
              placeholder="Search your notebook..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
        </Card>

        {/* Tabs */}
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="space-y-6"
        >
          <TabsList className="grid w-full grid-cols-3 lg:w-[400px]">
            <TabsTrigger value="articles" className="gap-2">
              <BookOpen className="h-4 w-4" /> Articles
            </TabsTrigger>
            <TabsTrigger value="quizzes" className="gap-2">
              <FileQuestion className="h-4 w-4" /> Quizzes
            </TabsTrigger>
            <TabsTrigger value="bookmarks" className="gap-2">
              <Bookmark className="h-4 w-4" /> Bookmarks
            </TabsTrigger>
          </TabsList>

          {/* Articles Tab */}
          <TabsContent value="articles" className="space-y-4">
            {filteredArticles && filteredArticles.length > 0 ? (
              <div className="space-y-4">
                {filteredArticles.map((article) => (
                  <ArticleCard
                    key={article.id}
                    article={article}
                    onDelete={refetchArticles}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                title={
                  searchQuery
                    ? "No articles found"
                    : "No articles generated yet"
                }
                description="Generate AI articles to build your personal knowledge base."
                actionLabel="Generate Article"
                onAction={() => router.push("/generate")}
              />
            )}
          </TabsContent>

          {/* Quizzes Tab */}
          <TabsContent value="quizzes" className="space-y-4">
            {filteredAttempts && filteredAttempts.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-6">
                {filteredAttempts.map((attempt) => (
                  <AttemptCard key={attempt.id} attempt={attempt} />
                ))}
              </div>
            ) : (
              <EmptyState
                title={
                  searchQuery ? "No quizzes found" : "No quizzes attempted yet"
                }
                description="Take quizzes to test your knowledge and track progress."
                actionLabel="Browse Quizzes"
                onAction={() => router.push("/assessment")}
              />
            )}
          </TabsContent>

          {/* Bookmarks Tab */}
          <TabsContent value="bookmarks" className="space-y-4">
            {filteredBookmarks && filteredBookmarks.length > 0 ? (
              <div className="space-y-4">
                {filteredBookmarks.map((bookmark) => (
                  <BookmarkCard
                    key={bookmark.id}
                    bookmark={bookmark}
                    onRemove={refetchBookmarks}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                title={
                  searchQuery ? "No bookmarks found" : "No bookmarks saved yet"
                }
                description="Bookmark interesting articles and quizzes to read later."
                actionLabel="Browse Topics"
                onAction={() => router.push("/topics")}
              />
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
