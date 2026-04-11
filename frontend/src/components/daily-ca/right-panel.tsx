"use client";

import Link from "next/link";
import { DailyCaArticleDetail } from "@/lib/api/daily-ca";
import { ConceptCard } from "./concept-card";

/**
 * RightPanel — contextual sidebar showing data for the focused article:
 *  - Related Articles (5, same subject)
 *  - Concepts Mentioned (from concept_links)
 *  - Explore Syllabus placeholder (Phase P+)
 */

interface Props {
  article: DailyCaArticleDetail | null;
}

const GS_COLORS: Record<string, string> = {
  GS1: "bg-purple-100 text-purple-700",
  GS2: "bg-blue-100 text-blue-700",
  GS3: "bg-green-100 text-green-700",
  GS4: "bg-orange-100 text-orange-700",
  CSAT: "bg-gray-100 text-gray-600",
};

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
  } catch {
    return dateStr;
  }
}

export function RightPanel({ article }: Props) {
  if (!article) {
    return (
      <aside className="space-y-4">
        <div className="rounded-xl border border-gray-200 bg-white p-4 h-40 flex items-center justify-center">
          <p className="text-xs text-gray-400 text-center">
            Select an article to see related content
          </p>
        </div>
      </aside>
    );
  }

  const relatedArticles = article.related_articles ?? [];
  const conceptLinks = article.concept_links ?? [];

  return (
    <aside className="space-y-4">
      {/* Related Articles */}
      {relatedArticles.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Related Articles
            </p>
            <p className="text-xs text-gray-400">{article.subject_name}</p>
          </div>
          <div className="divide-y divide-gray-50">
            {relatedArticles.slice(0, 5).map((rel) => {
              const gsColor = GS_COLORS[rel.gs_paper] ?? GS_COLORS["CSAT"];
              return (
                <Link
                  key={rel.id}
                  href={`/daily-ca/article/${rel.slug}`}
                  className="block px-4 py-3 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-1.5 mb-1">
                    {rel.gs_paper && (
                      <span
                        className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold ${gsColor}`}
                      >
                        {rel.gs_paper}
                      </span>
                    )}
                    <span className="text-[10px] text-gray-400">
                      {formatDate(rel.published_date)}
                    </span>
                  </div>
                  <p className="text-xs font-medium text-gray-800 leading-snug line-clamp-2">
                    {rel.title}
                  </p>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Concepts Mentioned */}
      {conceptLinks.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Concepts Mentioned
            </p>
            <p className="text-xs text-gray-400">
              {conceptLinks.length} concepts
            </p>
          </div>
          <div className="p-3 space-y-2">
            {conceptLinks.map((concept) => (
              <ConceptCard key={concept.id} concept={concept} />
            ))}
          </div>
        </div>
      )}

      {/* Explore Syllabus — placeholder */}
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="px-4 py-2.5 border-b border-gray-100">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Explore Syllabus
          </p>
        </div>
        <div className="p-4 flex items-center justify-center">
          <p className="text-xs text-gray-400 text-center">
            Static content library coming soon
          </p>
        </div>
      </div>
    </aside>
  );
}
