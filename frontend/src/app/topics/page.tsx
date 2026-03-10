/**
 * Topic browser page (ISR)
 */

import { subjectsAPI } from "@/lib/api/subjects";
import { topicsAPI } from "@/lib/api/topics";
import { BookOpen } from "lucide-react";
import TopicsClient from "./topics-client";

// Revalidate every hour
export const revalidate = 3600;

export default async function TopicsPage() {
  try {
    // Fetch data directly from API (Server Side)
    // We fetch a larger page size to ensure search works well for most topics
    const [topics, subjects] = await Promise.all([
      topicsAPI.list({ page_size: 200 }),
      subjectsAPI.list(),
    ]);

    return (
      <div className="container mx-auto px-4 py-8">
        {/* Header (Server Rendered) */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <BookOpen className="h-8 w-8 text-blue-600" />
              <h1 className="text-4xl font-bold font-heading tracking-tight">Topics</h1>
            </div>
          </div>

          <p className="text-gray-600 text-lg">
            Browse UPSC topics organized by subject and module
          </p>
        </div>

        {/* Client Side Components for Filtering and Viewing */}
        <TopicsClient initialTopics={topics} initialSubjects={subjects} />
      </div>
    );
  } catch (error) {
    console.error("Error loading topics in Server Component:", error);
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center text-red-600 bg-red-50 p-8 rounded-lg border border-red-100">
          <h3 className="text-lg font-semibold mb-2">Error Loading Topics</h3>
          <p>Please try again later. Check backend connectivity.</p>
        </div>
      </div>
    );
  }
}
