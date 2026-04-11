"use client";

import Link from "next/link";
import Image from "next/image";
import { DailyCaArticleList } from "@/lib/api/daily-ca";

/**
 * ArticleCard — used on tag pages and concept pages.
 * Shows: Date | Subject | GS badge | Title | News context | Hero image | "Read →"
 */

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
    return d.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

interface Props {
  article: DailyCaArticleList;
}

export function ArticleCard({ article }: Props) {
  const gsColor = GS_COLORS[article.gs_paper] ?? GS_COLORS["CSAT"];

  return (
    <Link
      href={`/daily-ca/article/${article.slug}`}
      className="group flex flex-col rounded-2xl border border-gray-200 bg-white overflow-hidden hover:border-blue-300 hover:shadow-md transition-all"
    >
      {/* Hero image */}
      {article.hero_image_url && (
        <div className="relative w-full h-40 bg-gray-100 flex-shrink-0">
          <Image
            src={article.hero_image_url}
            alt={article.title}
            fill
            className="object-cover"
            sizes="(max-width: 640px) 100vw, 50vw"
          />
        </div>
      )}

      {/* Content */}
      <div className="flex flex-col flex-1 p-4">
        {/* Meta row */}
        <div className="flex flex-wrap items-center gap-2 mb-2">
          {article.gs_paper && (
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${gsColor}`}
            >
              {article.gs_paper}
            </span>
          )}
          <span className="text-xs text-gray-500 truncate">
            {article.subject_name}
          </span>
          <span className="text-xs text-gray-300">·</span>
          <span className="text-xs text-gray-400">
            {formatDate(article.published_date)}
          </span>
        </div>

        {/* Title */}
        <h3 className="text-sm font-bold text-gray-900 leading-snug mb-1.5 line-clamp-2 group-hover:text-blue-700 transition-colors">
          {article.title}
        </h3>

        {/* News context */}
        {article.news_context && (
          <p className="text-xs text-gray-500 leading-relaxed line-clamp-2 flex-1">
            {article.news_context}
          </p>
        )}

        {/* Read link */}
        <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between">
          <div className="flex flex-wrap gap-1">
            {article.tags?.slice(0, 2).map((tag) => (
              <span
                key={tag.id}
                className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500"
              >
                #{tag.name}
              </span>
            ))}
          </div>
          <span className="text-xs font-semibold text-blue-600 group-hover:text-blue-800 flex-shrink-0">
            Read →
          </span>
        </div>
      </div>
    </Link>
  );
}
