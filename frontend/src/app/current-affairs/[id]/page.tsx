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
} from "lucide-react";
import { formatDate } from "@/lib/utils";
import Link from "next/link";
import { notFound } from "next/navigation";
import { abortIfApiUnreachable } from "@/lib/isr-guard";

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
      ordering: "-published_at",
    });
    return (list.results || []).map((article) => ({ id: article.id }));
  } catch (error) {
    // Returning [] used to be silent: the build stayed green and simply
    // prerendered NOTHING for this route. That is how the prerendered page
    // count moved 158 -> 238 between two builds a day apart with no signal
    // anywhere in the output (§5A.2). An outage now fails the build; a 4xx
    // still yields an empty list, because that is a real answer.
    abortIfApiUnreachable(error, "Current Affairs list (generateStaticParams)");

    console.error(
      "BUILD WARNING: generateStaticParams for Current Affairs returned no ids.",
      error,
    );
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
        {/* Rest of the valid page content... */}
        <div className="mb-10">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 mb-6">
            <h1 className="text-4xl md:text-5xl font-semibold text-foreground leading-tight tracking-tight">
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
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-5 bg-muted/40 rounded-xl border border-border mb-8 items-center">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5 text-muted-foreground text-xs font-bold uppercase">
                <Calendar className="h-3.5 w-3.5" /> Published
              </div>
              <span className="text-sm font-bold text-foreground">
                {formatDate(article.published_at)}
              </span>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5 text-muted-foreground text-xs font-bold uppercase">
                <User className="h-3.5 w-3.5" /> Source
              </div>
              <span className="text-sm font-bold text-foreground">
                {article.source_name}
              </span>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5 text-muted-foreground text-xs font-bold uppercase">
                <FileText className="h-3.5 w-3.5" /> Length
              </div>
              <span className="text-sm font-bold text-foreground">
                {article.word_count} Words
              </span>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5 text-muted-foreground text-xs font-bold uppercase">
                <ExternalLink className="h-3.5 w-3.5" /> Original
              </div>
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 font-bold text-sm hover:underline"
              >
                View Source
              </a>
            </div>
          </div>
        </div>

        {/* Categories */}
        {article.categories && article.categories.length > 0 && (
          <div className="mb-8 flex flex-wrap gap-2.5">
            {article.categories.map((category, idx) => (
              <Badge
                key={idx}
                variant="outline"
                className="px-3 py-1 bg-white hover:border-blue-300 font-medium text-gray-600"
              >
                {category}
              </Badge>
            ))}
          </div>
        )}

        {/* Summary */}
        {article.summary && (
          <div className="mb-10 bg-indigo-50 border-l-4 border-indigo-600 p-8 rounded-r-2xl shadow-sm">
            <h2 className="text-indigo-900 font-semibold uppercase text-xs tracking-widest mb-3">
              Key Synthesis
            </h2>
            <p className="text-indigo-900 text-lg leading-relaxed font-medium">
              {article.summary}
            </p>
          </div>
        )}

        {/* Content Section (Truncated for Legal Safety) */}
        <Card className="border-none shadow-none bg-white">
          <CardContent className="px-0 pt-0">
            <div className="prose prose-lg max-w-none prose-slate">
              <div className="whitespace-pre-wrap text-foreground leading-[1.8] text-xl font-serif">
                {article.content?.substring(0, 350)}
                {(article.content?.length || 0) > 350 && (
                  <span className="text-gray-500 font-sans text-sm block mt-6 p-4 bg-muted/40 rounded-lg border-l-4 border-gray-300">
                    ... [Analysis truncated for legal compliance. To read the
                    full in-depth coverage, please visit the original source:{" "}
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 font-bold hover:underline"
                    >
                      {article.source_name}
                    </a>
                    ]
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  } catch (error) {
    // An outage (no response / 5xx) aborts rather than caching an error page.
    //
    // The fallback that used to live here rendered a "Sync in Progress" spinner
    // AND injected `setTimeout(() => window.location.reload(), 10000)`. With
    // revalidate = 86400 that fallback is cached for 24 h, so every visitor to
    // an affected article reloaded every 10 s and was served the same cached
    // page again — a self-inflicted request amplifier on a quota already over
    // budget. Throwing instead means Next never caches the failure and the next
    // request retries cleanly (§5A.4a).
    abortIfApiUnreachable(error, "CA API");

    // 4xx: the API answered and this article is gone. Data, not an outage.
    console.warn(`CA article ${articleId} unavailable — rendering 404.`);
    notFound();
  }
}
