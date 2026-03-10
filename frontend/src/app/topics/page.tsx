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

        {/* Sync Status */}
        <div className="mt-12 pt-4 border-t border-gray-100 flex justify-between items-center text-[10px] text-gray-400 uppercase tracking-widest font-bold">
          <div className="flex items-center gap-2">
            <div className={`h-1.5 w-1.5 rounded-full ${topics.length > 0 ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`} />
            {topics.length > 0 ? 'Live Sync Active (1h)' : 'Standby Mode: Waiting for Backend'}
          </div>
          <div>
            Snapshot Time: {new Date().toLocaleTimeString()}
          </div>
        </div>
      </div>
    );
  } catch (error) {
    console.error("ISR Fetch Failed for Topics (Likely Render 503). Falling back to Client-side fetch.", error);
    
    return (
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <BookOpen className="h-8 w-8 text-blue-600" />
            <h1 className="text-4xl font-bold font-heading tracking-tight">Topics</h1>
          </div>
          <div className="p-4 bg-amber-50 rounded-lg border border-amber-100 flex items-center gap-3 text-amber-800 text-sm">
            <div className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
            Connecting to Intelligence Categories... (Service recovering)
          </div>
        </div>
        <TopicsClient initialTopics={[]} initialSubjects={[]} />
      </div>
    );
  }
}
