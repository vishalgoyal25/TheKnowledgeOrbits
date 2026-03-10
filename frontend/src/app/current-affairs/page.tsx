/**
 * Current Affairs Home Page (ISR)
 */

import { currentAffairsAPI } from "@/lib/api/current-affairs";
import { Newspaper, LayoutGrid, Settings } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import CurrentAffairsClient from "./ca-client";

// Revalidate every 10 minutes to catch new Ghost worker updates
export const revalidate = 600;

export default async function CurrentAffairsPage() {
  try {
    // Fetch initial data on the server
    const [articlesData, sourcesData] = await Promise.all([
      currentAffairsAPI.listArticles({ limit: 20, ordering: "-published_at" }),
      currentAffairsAPI.listSources(),
    ]);

    const initialArticles = articlesData?.results || [];
    const initialTotal = articlesData?.count || 0;
    const sources = sourcesData?.results || [];

    return (
      <div className="container mx-auto px-4 py-8">
        {/* Header (Server Rendered) */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <Newspaper className="h-8 w-8 text-blue-600" />
              <h1 className="text-4xl font-bold font-heading tracking-tight">Current Affairs</h1>
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
      </div>
    );
  } catch (error) {
    console.error("Error loading Current Affairs in Server Component:", error);
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center text-red-600 bg-red-50 p-8 rounded-lg border border-red-100">
          <h3 className="text-lg font-semibold mb-2">Error Loading Current Affairs</h3>
          <p>Please try again later. Check backend connectivity.</p>
        </div>
      </div>
    );
  }
}
