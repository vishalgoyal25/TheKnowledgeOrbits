/**
 * Current Affairs Home Page (ISR)
 */

import { currentAffairsAPI } from "@/lib/api/current-affairs";
import { Newspaper, LayoutGrid, Settings } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import CurrentAffairsClient from "./ca-client";
import { CAArticle, CASource } from "@/lib/types";

// Revalidate every 10 minutes to catch new Ghost worker updates
export const revalidate = 600;

export default async function CurrentAffairsPage() {
  let initialArticles: CAArticle[] = [];
  let initialTotal = 0;
  let sources: CASource[] = [];

  try {
    // Fetch initial data on the server
    const [articlesData, sourcesData] = await Promise.all([
      currentAffairsAPI.listArticles({ limit: 20, ordering: "-published_at" }),
      currentAffairsAPI.listSources(),
    ]);

    initialArticles = (articlesData?.results || []) as CAArticle[];
    initialTotal = articlesData?.count || 0;
    sources = (sourcesData?.results || []) as CASource[];
  } catch (error) {
    console.warn("Build-time fetch failed for Current Affairs:", error);
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
      "CA data missing during ISR build - Aborting to protect cache",
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header (Server Rendered) */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <Newspaper className="h-8 w-8 text-blue-600" />
            <h1 className="text-4xl font-bold font-heading tracking-tight">
              Current Affairs
            </h1>
          </div>

          <div className="flex items-center gap-2">
            <Link href="/current-affairs/chunks">
              <Button variant="outline" className="gap-2">
                <LayoutGrid className="h-4 w-4" />
                View Chunks
              </Button>
            </Link>

            <Link href="/current-affairs/sources">
              <Button variant="outline" className="gap-2">
                <Settings className="h-4 w-4" />
                Sources
              </Button>
            </Link>
          </div>
        </div>

        <p className="text-gray-600 text-lg">
          Stay updated with latest news integrated into UPSC preparation
        </p>
      </div>

      {/* Client Side Components for Filtering and Viewing */}
      <CurrentAffairsClient
        initialArticles={initialArticles}
        initialTotal={initialTotal}
        sources={sources}
      />

      {/* Sync Status (Visible in footer) */}
      <div className="mt-12 pt-4 border-t border-gray-100 flex justify-between items-center text-[10px] text-gray-400 uppercase tracking-widest font-bold">
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          Live Sync Active (10m)
        </div>
        <div>Snapshot Time: {new Date().toLocaleTimeString()}</div>
      </div>
    </div>
  );
}
