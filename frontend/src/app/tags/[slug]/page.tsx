"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getTagDetail, getTagArticles, TagDetail } from "@/lib/api/tags";
import { DailyCaArticleList } from "@/lib/api/daily-ca";
import { ArticleCard } from "@/components/daily-ca/article-card";

const TAG_TYPE_COLORS: Record<string, string> = {
  topic: "bg-blue-100 text-blue-700",
  subtopic: "bg-sky-100 text-sky-700",
  scheme: "bg-green-100 text-green-700",
  law: "bg-purple-100 text-purple-700",
  person: "bg-orange-100 text-orange-700",
  place: "bg-teal-100 text-teal-700",
  organisation: "bg-indigo-100 text-indigo-700",
  concept: "bg-slate-100 text-slate-700",
  event: "bg-amber-100 text-amber-700",
  other: "bg-gray-100 text-gray-600",
};

const PAGE_SIZE = 20;

export default function TagPage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();

  const [tag, setTag] = useState<TagDetail | null>(null);
  const [articles, setArticles] = useState<DailyCaArticleList[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [articlesLoading, setArticlesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch tag metadata once
  const fetchTag = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getTagDetail(slug);
      setTag(data);
    } catch {
      setError("Tag not found.");
    } finally {
      setLoading(false);
    }
  }, [slug]);

  // Fetch articles for current page
  const fetchArticles = useCallback(
    async (currentOffset: number) => {
      if (!slug) return;
      setArticlesLoading(true);
      try {
        const data = await getTagArticles(slug, PAGE_SIZE, currentOffset);
        setArticles(data.results);
        setTotal(data.total);
      } catch {
        // keep existing articles
      } finally {
        setArticlesLoading(false);
      }
    },
    [slug],
  );

  useEffect(() => {
    fetchTag();
  }, [fetchTag]);
  useEffect(() => {
    fetchArticles(offset);
  }, [fetchArticles, offset]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  const handlePrev = () => {
    const newOffset = Math.max(0, offset - PAGE_SIZE);
    setOffset(newOffset);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleNext = () => {
    if (offset + PAGE_SIZE < total) {
      setOffset(offset + PAGE_SIZE);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  // ── Loading ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-5xl mx-auto px-4 py-10 space-y-6">
          <div className="h-8 bg-gray-200 rounded animate-pulse w-1/3" />
          <div className="h-4 bg-gray-100 rounded animate-pulse w-2/3" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-52 bg-white rounded-2xl border border-gray-200 animate-pulse"
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error || !tag) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-4xl mb-4">🏷️</p>
          <p className="text-gray-700 font-semibold mb-2">
            {error ?? "Tag not found"}
          </p>
          <button
            onClick={() => router.push("/daily-ca")}
            className="text-sm text-blue-600 hover:underline"
          >
            ← Back to Daily CA
          </button>
        </div>
      </div>
    );
  }

  const typeColor = TAG_TYPE_COLORS[tag.tag_type] ?? TAG_TYPE_COLORS.other;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-8">
          {/* Breadcrumb */}
          <button
            onClick={() => router.push("/daily-ca")}
            className="text-xs text-gray-400 hover:text-blue-600 mb-4 flex items-center gap-1 transition-colors"
          >
            ← Daily CA
          </button>

          {/* Tag name + meta */}
          <div className="flex flex-wrap items-start gap-3 mb-3">
            <h1 className="text-2xl font-bold text-gray-900">#{tag.name}</h1>
            <span
              className={`mt-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${typeColor}`}
            >
              {tag.tag_type}
            </span>
          </div>

          {tag.description && (
            <p className="text-sm text-gray-600 leading-relaxed max-w-2xl mb-3">
              {tag.description}
            </p>
          )}

          <p className="text-xs text-gray-400">
            <span className="font-semibold text-gray-600">{total}</span> article
            {total !== 1 ? "s" : ""} tagged with this keyword
          </p>
        </div>
      </div>

      {/* Articles */}
      <div className="max-w-5xl mx-auto px-4 py-6">
        {articlesLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {Array.from({ length: PAGE_SIZE }).map((_, i) => (
              <div
                key={i}
                className="h-52 bg-white rounded-2xl border border-gray-200 animate-pulse"
              />
            ))}
          </div>
        ) : articles.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-4xl mb-4">📭</p>
            <p className="text-gray-500">
              No published articles for this tag yet.
            </p>
          </div>
        ) : (
          <>
            {/* Sort label */}
            <div className="flex items-center justify-between mb-4">
              <p className="text-xs text-gray-400">
                Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of{" "}
                {total} · newest first
              </p>
            </div>

            {/* Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
              {articles.map((article) => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4">
                <button
                  onClick={handlePrev}
                  disabled={offset === 0}
                  className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-blue-600 disabled:opacity-30 disabled:cursor-not-allowed border border-gray-200 rounded-xl px-4 py-2 transition-colors hover:border-blue-300"
                >
                  ← Previous
                </button>
                <span className="text-sm text-gray-500">
                  Page{" "}
                  <span className="font-semibold text-gray-800">
                    {currentPage}
                  </span>{" "}
                  of{" "}
                  <span className="font-semibold text-gray-800">
                    {totalPages}
                  </span>
                </span>
                <button
                  onClick={handleNext}
                  disabled={offset + PAGE_SIZE >= total}
                  className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-blue-600 disabled:opacity-30 disabled:cursor-not-allowed border border-gray-200 rounded-xl px-4 py-2 transition-colors hover:border-blue-300"
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
