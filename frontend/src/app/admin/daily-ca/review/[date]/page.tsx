"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getAdminArticles,
  publishDate,
  AdminArticle,
} from "@/lib/api/daily-ca-admin";

function QualityBadge({ score }: { score: number }) {
  const color =
    score >= 8
      ? "bg-green-100 text-green-700"
      : score >= 6
        ? "bg-yellow-100 text-yellow-700"
        : "bg-red-100 text-red-700";
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${color}`}>
      {score.toFixed(1)}/10
    </span>
  );
}

function PreviewModal({
  article,
  onClose,
}: {
  article: AdminArticle;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-start justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="font-bold text-gray-900 text-base leading-snug pr-4">
            {article.title}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 text-2xl leading-none flex-shrink-0"
          >
            ×
          </button>
        </div>
        <div className="px-6 py-4">
          {/* Meta */}
          <div className="flex flex-wrap gap-2 mb-4">
            {article.gs_paper && (
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                {article.gs_paper}
              </span>
            )}
            {article.subject_name && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                {article.subject_name}
              </span>
            )}
            <QualityBadge score={article.quality_score} />
            <span className="text-xs text-gray-400">
              {article.published_date}
            </span>
          </div>

          {/* News context */}
          {article.news_context && (
            <div className="bg-blue-50 rounded-xl p-3 mb-4 text-sm text-blue-800">
              <span className="font-semibold">News context: </span>
              {article.news_context}
            </div>
          )}

          {/* Body */}
          <div className="prose prose-sm max-w-none text-gray-800 whitespace-pre-wrap text-sm leading-relaxed border-t border-gray-100 pt-4">
            {article.body_md_processed || "No content yet."}
          </div>

          {/* Tags */}
          {article.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-4 pt-4 border-t border-gray-100">
              {article.tags.map((t) => (
                <span
                  key={t.id}
                  className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600"
                >
                  #{t.name}
                </span>
              ))}
            </div>
          )}

          {/* Concepts */}
          {article.concept_links.length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-gray-400 mb-1">
                Concept links ({article.concept_links.length})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {article.concept_links.map((c) => (
                  <span
                    key={c.id}
                    className="text-xs px-2 py-0.5 rounded-full bg-purple-50 text-purple-700"
                  >
                    {c.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Generation metadata */}
          <div className="mt-4 pt-4 border-t border-gray-100">
            <p className="text-xs text-gray-400 font-semibold mb-1">
              Generation Metadata
            </p>
            <pre className="text-xs text-gray-500 bg-gray-50 rounded-lg p-2 overflow-x-auto">
              {JSON.stringify(article.generation_metadata, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const date = params.date as string;

  const [articles, setArticles] = useState<AdminArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState<string | null>(null);
  const [preview, setPreview] = useState<AdminArticle | null>(null);

  const fetchArticles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAdminArticles(date);
      setArticles(data.articles);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load articles");
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => {
    fetchArticles();
  }, [fetchArticles]);

  const handlePublishAll = async () => {
    setPublishing(true);
    setError(null);
    try {
      const res = await publishDate(date);
      setPublishResult(`✓ ${res.published} article(s) published successfully!`);
      fetchArticles();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Publish failed");
    } finally {
      setPublishing(false);
    }
  };

  const unpublished = articles.filter((a) => !a.is_published);
  const published = articles.filter((a) => a.is_published);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/admin/daily-ca/proposals")}
              className="text-gray-400 hover:text-gray-700 text-sm"
            >
              ← Proposals
            </button>
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                Article Review — {date}
              </h1>
              <p className="text-sm text-gray-500">
                {unpublished.length} unpublished · {published.length} published
              </p>
            </div>
          </div>
          {unpublished.length > 0 && (
            <button
              onClick={handlePublishAll}
              disabled={publishing}
              className="bg-green-600 hover:bg-green-700 disabled:bg-green-300 text-white font-semibold px-5 py-2.5 rounded-xl transition-colors flex items-center gap-2"
            >
              {publishing ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />{" "}
                  Publishing...
                </>
              ) : (
                `Publish All (${unpublished.length})`
              )}
            </button>
          )}
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* Success message */}
        {publishResult && (
          <div className="mb-4 bg-green-50 border border-green-200 text-green-700 rounded-xl px-4 py-3 text-sm flex items-center justify-between">
            <span>{publishResult}</span>
            <button
              onClick={() => setPublishResult(null)}
              className="text-green-500 hover:text-green-700"
            >
              ×
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-20 text-gray-400">
            Loading articles...
          </div>
        ) : articles.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-500 mb-2">No articles found for {date}</p>
            <p className="text-sm text-gray-400">
              Run the generate command first:{" "}
              <code className="bg-gray-100 px-1 rounded">
                python manage.py generate_daily_ca --date {date}
              </code>
            </p>
          </div>
        ) : (
          <>
            {/* Unpublished articles */}
            {unpublished.length > 0 && (
              <>
                <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
                  Ready to Publish ({unpublished.length})
                </h2>
                <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden mb-6">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-100">
                      <tr>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                          Title
                        </th>
                        <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide hidden sm:table-cell">
                          GS
                        </th>
                        <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide hidden md:table-cell">
                          Words
                        </th>
                        <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                          Quality
                        </th>
                        <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide hidden md:table-cell">
                          Tags
                        </th>
                        <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide hidden md:table-cell">
                          Concepts
                        </th>
                        <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                          Action
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {unpublished.map((article) => {
                        const wordCount =
                          (article.generation_metadata?.word_count as number) ||
                          0;
                        return (
                          <tr
                            key={article.id}
                            className="hover:bg-gray-50 transition-colors"
                          >
                            <td className="px-4 py-3">
                              <p className="font-medium text-gray-900 line-clamp-1">
                                {article.title}
                              </p>
                              <p className="text-xs text-gray-400 mt-0.5">
                                {article.subject_name}
                              </p>
                            </td>
                            <td className="px-3 py-3 text-center hidden sm:table-cell">
                              {article.gs_paper && (
                                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                                  {article.gs_paper}
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-3 text-center text-xs text-gray-500 hidden md:table-cell">
                              {wordCount > 0 ? wordCount : "—"}
                            </td>
                            <td className="px-3 py-3 text-center">
                              <QualityBadge score={article.quality_score} />
                            </td>
                            <td className="px-3 py-3 text-center text-xs text-gray-500 hidden md:table-cell">
                              {article.tags.length}
                            </td>
                            <td className="px-3 py-3 text-center text-xs text-gray-500 hidden md:table-cell">
                              {article.concept_links.length}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <button
                                onClick={() => setPreview(article)}
                                className="text-xs text-blue-600 hover:underline font-medium"
                              >
                                Preview
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {/* Published articles */}
            {published.length > 0 && (
              <>
                <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  Already Published ({published.length})
                </h2>
                <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
                  <table className="w-full text-sm">
                    <tbody className="divide-y divide-gray-50">
                      {published.map((article) => (
                        <tr key={article.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3">
                            <p className="font-medium text-gray-700 line-clamp-1">
                              {article.title}
                            </p>
                            <p className="text-xs text-gray-400 mt-0.5">
                              {article.subject_name}
                            </p>
                          </td>
                          <td className="px-3 py-3 text-center">
                            <span className="text-xs text-green-600 font-semibold">
                              ✓ Live
                            </span>
                          </td>
                          <td className="px-3 py-3 text-center">
                            <QualityBadge score={article.quality_score} />
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => setPreview(article)}
                              className="text-xs text-blue-600 hover:underline font-medium"
                            >
                              Preview
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
      </div>

      {/* Preview Modal */}
      {preview && (
        <PreviewModal article={preview} onClose={() => setPreview(null)} />
      )}
    </div>
  );
}
