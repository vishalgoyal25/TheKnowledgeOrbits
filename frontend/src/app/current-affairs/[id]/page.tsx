/**
 * CA Article Detail Page (ISR/SSG)
 */

import { currentAffairsAPI } from "@/lib/api/current-affairs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  ArrowLeft,
  ExternalLink,
  Calendar,
  User,
  FileText,
  Loader2,
} from "lucide-react";
import { formatDate } from "@/lib/utils";
import Link from "next/link";

// Revalidate once a day (CA articles don't change once published)
export const revalidate = 86400;

// This is the secret for the 1 Lakh archive: 
// Allow on-demand generation for items not pre-built
export const dynamicParams = true;

// Pre-render only the Latest 100 news items for building stability
// (Others will be built on-demand via ISR)
export async function generateStaticParams() {
  try {
    const list = await currentAffairsAPI.listArticles({ 
      limit: 100, 
      ordering: "-published_at" 
    });
    return (list.results || []).map((article) => ({ id: article.id }));
  } catch (error) {
    console.error("BUILD WARNING: generateStaticParams for Current Affairs failed (likely Render timeout). Skipping pre-build.", error);
    return [];
  }
}

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function CAArticleDetailPage({ params }: PageProps) {
  const { id: articleId } = await params;

  try {
    const article = await currentAffairsAPI.getArticle(articleId);

    if (!article) {
      throw new Error("Article Sync Delayed");
    }

    return (
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {/* Back button */}
        <Link href="/current-affairs">
          <Button variant="ghost" className="mb-6 gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Current Affairs
          </Button>
        </Link>

        {/* Article Header */}
        <div className="mb-10">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 mb-6">
            <h1 className="text-4xl md:text-5xl font-black text-gray-900 leading-tight tracking-tight">
              {article.title}
            </h1>

            <div className="shrink-0">
              <Badge
                className={`px-4 py-1.5 text-xs font-bold uppercase tracking-wider shadow-sm border-none ${
                  article.processing_status === "completed"
                    ? "bg-emerald-600 text-white"
                    : article.processing_status === "processing"
                      ? "bg-blue-600 text-white"
                      : article.processing_status === "pending"
                        ? "bg-amber-500 text-white"
                        : "bg-red-600 text-white"
                }`}
              >
                {article.processing_status}
              </Badge>
            </div>
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-5 bg-gray-50 rounded-xl border border-gray-100 mb-8 items-center">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5 text-gray-400 text-xs font-bold uppercase">
                <Calendar className="h-3.5 w-3.5" /> Published
              </div>
              <span className="text-sm font-bold text-gray-800">{formatDate(article.published_at)}</span>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5 text-gray-400 text-xs font-bold uppercase">
                <User className="h-3.5 w-3.5" /> Source
              </div>
              <span className="text-sm font-bold text-gray-800">{article.source_name}</span>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5 text-gray-400 text-xs font-bold uppercase">
                <FileText className="h-3.5 w-3.5" /> Length
              </div>
              <span className="text-sm font-bold text-gray-800">{article.word_count} Words</span>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5 text-gray-400 text-xs font-bold uppercase">
                <ExternalLink className="h-3.5 w-3.5" /> Original
              </div>
              <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 font-bold text-sm hover:underline">
                View Source
              </a>
            </div>
          </div>
        </div>

        {/* Categories */}
        {article.categories && article.categories.length > 0 && (
          <div className="mb-8 flex flex-wrap gap-2.5">
            {article.categories.map((category, idx) => (
              <Badge key={idx} variant="outline" className="px-3 py-1 bg-white hover:border-blue-300 font-medium text-gray-600">
                {category}
              </Badge>
            ))}
          </div>
        )}

        {/* Summary */}
        {article.summary && (
          <div className="mb-10 bg-indigo-50 border-l-4 border-indigo-600 p-8 rounded-r-2xl shadow-sm">
            <h2 className="text-indigo-900 font-black uppercase text-xs tracking-widest mb-3">Key Synthesis</h2>
            <p className="text-indigo-900 text-lg leading-relaxed font-medium">{article.summary}</p>
          </div>
        )}

        {/* Content */}
        <Card className="border-none shadow-none bg-white">
          <CardContent className="px-0 pt-0">
            <div className="prose prose-lg max-w-none prose-slate">
              <div className="whitespace-pre-wrap text-gray-800 leading-[1.8] text-xl font-serif">
                {article.content}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Floating Back to Top Button or similar could go here */}
      </div>
    );
  } catch (error) {
    console.error("Error loading CA article in Server Component:", error);
    
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <div className="max-w-md mx-auto p-8 bg-blue-50 rounded-2xl border border-blue-100 shadow-sm">
          <div className="h-12 w-12 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
          <h2 className="text-xl font-bold text-blue-900 mb-2">Sync in Progress...</h2>
          <p className="text-blue-700 mb-6 font-medium">
            The News Engine is currently synchronizing this article. Please wait a few moments...
          </p>
          <div className="flex flex-col gap-3">
            <Link href="/current-affairs" className="text-sm text-blue-600 font-bold hover:underline py-2 uppercase tracking-tight">
              Back to News List
            </Link>
          </div>
        </div>
        <script dangerouslySetInnerHTML={{ 
          __html: `setTimeout(() => window.location.reload(), 5000)` 
        }} />
      </div>
    );
  }
}
