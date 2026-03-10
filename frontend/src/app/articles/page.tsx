/**
 * Article listing page (ISR/Resilient)
 */

import { articlesAPI } from "@/lib/api/articles";
import { Sparkles } from "lucide-react";
import ArticlesClient from "./articles-client";

// Revalidate every hour
export const revalidate = 3600;

export default async function ArticlesPage() {
  try {
    // Fetch initial data on the server
    const response = await articlesAPI.list({ limit: 20, ordering: "-created_at" });

    const initialArticles = response?.results || [];
    const initialTotal = response?.count || 0;

    return (
      <div className="container mx-auto px-4 py-8">
        {/* Header (Server Rendered) */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Sparkles className="h-8 w-8 text-blue-600" />
            <h1 className="text-4xl font-bold font-heading tracking-tight">Articles</h1>
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
            <div className={`h-1.5 w-1.5 rounded-full ${initialArticles.length > 0 ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`} />
            {initialArticles.length > 0 ? 'Live Sync Active (1h)' : 'Standby Mode: Waiting for Backend'}
          </div>
          <div>
            Snapshot Time: {new Date().toLocaleTimeString()}
          </div>
        </div>
      </div>
    );
  } catch (error) {
    console.error("ISR Fetch Failed for Articles (Likely Render 503). Falling back to Client-side fetch.", error);
    
    // Fallback: Still render the client component, but let IT handle the fetch
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Sparkles className="h-8 w-8 text-blue-600" />
            <h1 className="text-4xl font-bold font-heading tracking-tight">Articles</h1>
          </div>
          <div className="p-4 bg-amber-50 rounded-lg border border-amber-100 flex items-center gap-3 text-amber-800 text-sm">
            <div className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
            Service recovering from standby... retrying connection.
          </div>
        </div>
        <ArticlesClient 
          initialArticles={[]} 
          initialTotal={0} 
        />
      </div>
    );
  }
}
