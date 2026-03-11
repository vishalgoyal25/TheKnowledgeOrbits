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
  // Fetch data directly from API (Server Side)
  const [topics, subjects] = await Promise.all([
    topicsAPI.list({ page_size: 200 }),
    subjectsAPI.list(),
  ]);

  // CRITICAL: Total Content Guard (Anti-Poison Logic)
  // If we have no topics during an ISR build/revalidation, we MUST throw.
  // This tells Next.js NOT to cache this empty state, preserving the last good version.
  if (topics.length === 0) {
    throw new Error(
      "Topics data missing during ISR build - Aborting to protect cache",
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header (Server Rendered) */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <BookOpen className="h-8 w-8 text-blue-600" />
            <h1 className="text-4xl font-bold font-heading tracking-tight">
              Topics
            </h1>
          </div>
        </div>

        <p className="text-gray-600 text-lg">
          Browse UPSC topics organized by subject and module
        </p>
      </div>

      {/* Client Side Components for Filtering and Viewing */}
      <TopicsClient initialTopics={topics} initialSubjects={subjects} />

      {/* Sync Status */}
      <div className="mt-12 pt-4 border-t border-gray-100 flex justify-between items-center text-[10px] text-gray-400 uppercase tracking-widest font-bold">
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          Live Sync Active (1h)
        </div>
        <div>Snapshot Time: {new Date().toLocaleTimeString()}</div>
      </div>
    </div>
  );
}
