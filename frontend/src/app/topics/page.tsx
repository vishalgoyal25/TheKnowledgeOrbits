/**
 * Topic browser page (ISR)
 */

import { subjectsAPI } from "@/lib/api/subjects";
import { topicsAPI } from "@/lib/api/topics";
import { BookOpen } from "lucide-react";
import TopicsClient from "./topics-client";
import { Topic, Subject } from "@/lib/types";

// Revalidate every hour
export const revalidate = 3600;

export default async function TopicsPage() {
  let topics: Topic[] = [];
  let subjects: Subject[] = [];

  try {
    // Fetch data directly from API (Server Side)
    const [topicsRes, subjectsRes] = await Promise.all([
      topicsAPI.list({ page_size: 200 }),
      subjectsAPI.list(),
    ]);
    topics = (topicsRes || []) as Topic[];
    subjects = (subjectsRes || []) as Subject[];
  } catch (error) {
    console.warn("Build-time fetch failed for Topics:", error);
    // CRITICAL: ONLY throw if the actual fetch failed during build/revalidation.
    if (process.env.SKIP_BACKEND_WAIT !== "true") {
      throw new Error(
        "Topics API unreachable during ISR build - Aborting to protect cache",
      );
    }
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
