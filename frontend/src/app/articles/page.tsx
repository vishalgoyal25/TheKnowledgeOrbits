/**
 * Article listing page (ISR/Resilient)
 */

import { articlesAPI } from "@/lib/api/articles";
import { Sparkles } from "lucide-react";
import ArticlesClient from "./articles-client";

// Revalidate every hour
export const revalidate = 3600;

import { Article } from "@/lib/types";

export default async function ArticlesPage() {
  let initialArticles: Article[] = [];
  let initialTotal = 0;

  try {
    const response = await articlesAPI.list({
      limit: 20,
      ordering: "-created_at",
    });

    initialArticles = response?.results || [];
    initialTotal = response?.count || 0;
  } catch (error) {
    console.warn("Build-time fetch failed for Articles:", error);
  }

  // CRITICAL: Total Content Guard (Anti-Poison Logic)
  // If we have no articles during an ISR build/revalidation, we MUST throw.
  // This tells Next.js NOT to cache this empty state, preserving the last good version.
  // We bypass this ONLY during CI (SKIP_BACKEND_WAIT=true) to allow build integrity checks.
  if (
    initialArticles.length === 0 &&
    process.env.SKIP_BACKEND_WAIT !== "true"
  ) {
    throw new Error(
      "Articles data missing during ISR build - Aborting to protect cache",
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header (Server Rendered) */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Sparkles className="h-8 w-8 text-blue-600" />
          <h1 className="text-4xl font-bold font-heading tracking-tight">
            Articles
          </h1>
        </div>
        <p className="text-gray-600 text-lg">
          Browse AI-generated articles on UPSC topics
        </p>
      </div>

      {/* Client Side Components for Filtering and Viewing */}
      <ArticlesClient
        initialArticles={initialArticles}
        initialTotal={initialTotal}
      />

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
