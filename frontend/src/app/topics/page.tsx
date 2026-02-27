/**
 * Topic browser page
 */

"use client";

import { useState } from "react";
import { useTopics } from "@/lib/hooks/use-topics";
import { useSubjects } from "@/lib/hooks/use-subjects";
import TopicCard from "@/components/topics/topic-card";
import TopicTree from "@/components/topics/topic-tree";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Search, Filter, LayoutGrid, List } from "lucide-react";

export default function TopicsPage() {
  const [searchTerm, setSearchTerm] = useState("");

  const {
    data: topicsData,
    isLoading: topicsLoading,
    error: topicsError,
  } = useTopics({
    page_size: 50,
  });
  const { data: subjectsData, isLoading: subjectsLoading } = useSubjects();

  const isLoading = topicsLoading || subjectsLoading;

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <Skeleton className="h-10 w-48 mb-2" />
          <Skeleton className="h-5 w-96" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      </div>
    );
  }

  if (topicsError) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center text-red-600 bg-red-50 p-8 rounded-lg border border-red-100">
          <h3 className="text-lg font-semibold mb-2">Error Loading Topics</h3>
          <p>Please try again later.</p>
        </div>
      </div>
    );
  }

  const topics = Array.isArray(topicsData)
    ? topicsData
    : (topicsData as any)?.results || [];
  const subjects = Array.isArray(subjectsData)
    ? subjectsData
    : (subjectsData as any)?.results || [];

  // Client-side filter
  const filteredTopics = topics.filter(
    (topic: any) =>
      topic.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      topic.description?.toLowerCase().includes(searchTerm.toLowerCase()),
  );

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Topics</h1>
        <p className="text-gray-600">
          Browse UPSC topics organized by subject and module
        </p>
      </div>

      {/* Filters */}
      <div className="mb-8 flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search topics..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>

        <Button variant="outline" className="gap-2">
          <Filter className="h-4 w-4" />
          Filter
        </Button>
      </div>

      {/* View Toggle & Content */}
      <Tabs defaultValue="grid" className="w-full">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
          <p className="text-sm text-gray-600">
            Showing {filteredTopics.length} of {topics.length} topics across{" "}
            {subjects.length} subjects
          </p>

          <TabsList>
            <TabsTrigger value="grid" className="gap-2">
              <LayoutGrid className="h-4 w-4" />
              Grid
            </TabsTrigger>
            <TabsTrigger value="tree" className="gap-2">
              <List className="h-4 w-4" />
              Tree
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Grid View */}
        <TabsContent value="grid">
          {filteredTopics.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed">
              <p className="text-gray-600">
                No topics found matching your search.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredTopics.map((topic: any) => (
                <TopicCard key={topic.id} topic={topic} />
              ))}
            </div>
          )}
        </TabsContent>

        {/* Tree View */}
        <TabsContent value="tree">
          {filteredTopics.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed">
              <p className="text-gray-600">
                No topics found matching your search.
              </p>
            </div>
          ) : (
            <div className="max-w-4xl border rounded-lg p-4 bg-white shadow-sm">
              <TopicTree topics={filteredTopics} />
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
