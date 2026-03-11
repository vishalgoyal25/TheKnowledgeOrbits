"use client";

import { useState } from "react";
import TopicCard from "@/components/topics/topic-card";
import TopicTree from "@/components/topics/topic-tree";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Filter, LayoutGrid, List, Search } from "lucide-react";
import { Topic, Subject } from "@/lib/types";

import { useTopics } from "@/lib/hooks/use-topics";
import { useSubjects } from "@/lib/hooks/use-subjects";

interface TopicsClientProps {
  initialTopics: Topic[];
  initialSubjects: Subject[];
}

export default function TopicsClient({
  initialTopics,
  initialSubjects,
}: TopicsClientProps) {
  const [searchTerm, setSearchTerm] = useState("");

  // Determine if we should use server-side initial data
  const isInitialState =
    searchTerm === "" && initialTopics.length > 0 && initialSubjects.length > 0;

  // Client-side query fallback (only enabled if we've deviated from initial server state or server failed)
  const { data: topicsData, isLoading: isTopicsLoading } = useTopics({
    page_size: 200,
  });
  const { data: subjectsData, isLoading: isSubjectsLoading } = useSubjects();

  // Extract arrays, falling back to initial data if available and in initial state
  const topics = isInitialState ? initialTopics : topicsData || [];
  const activeSubjects = isInitialState ? initialSubjects : subjectsData || [];

  const isLoading = (isTopicsLoading || isSubjectsLoading) && !isInitialState;

  const filteredTopics = topics.filter(
    (topic: Topic) =>
      topic.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      topic.description?.toLowerCase().includes(searchTerm.toLowerCase()),
  );

  return (
    <>
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-blue-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Total Topics</div>
          <div className="text-3xl font-bold text-blue-600">
            {initialTopics.length}
          </div>
        </div>

        <div className="bg-green-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Active Subjects</div>
          <div className="text-3xl font-bold text-green-600">
            {activeSubjects.length}
          </div>
        </div>

        <div className="bg-purple-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Showing</div>
          <div className="text-3xl font-bold text-purple-600">
            {filteredTopics.length}
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="mb-8 p-4 bg-blue-50 border border-blue-100 rounded-lg flex items-center gap-3 text-blue-800 animate-pulse">
          <div className="h-2 w-2 rounded-full bg-blue-500 animate-bounce" />
          Synchronizing intelligence categories from backup network...
        </div>
      )}

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
        <TabsList className="mb-6">
          <TabsTrigger value="grid" className="gap-2">
            <LayoutGrid className="h-4 w-4" />
            Grid
          </TabsTrigger>
          <TabsTrigger value="tree" className="gap-2">
            <List className="h-4 w-4" />
            Tree
          </TabsTrigger>
        </TabsList>

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
              {filteredTopics.map((topic) => (
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
    </>
  );
}
