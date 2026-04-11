"use client";

import { useRouter } from "next/navigation";
import { DailyCaArticleDetail } from "@/lib/api/daily-ca";

/**
 * LeftPanel — collapsible sidebar with:
 *  - Date display + calendar navigation
 *  - Table of Contents (ToC) with active article highlight
 */

const GS_COLORS: Record<string, string> = {
  GS1: "bg-purple-100 text-purple-700",
  GS2: "bg-blue-100 text-blue-700",
  GS3: "bg-green-100 text-green-700",
  GS4: "bg-orange-100 text-orange-700",
  CSAT: "bg-gray-100 text-gray-600",
};

interface Props {
  articles: DailyCaArticleDetail[];
  activeId: string | null;
  date: string;
  onArticleClick: (id: string) => void;
}

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

export function LeftPanel({ articles, activeId, date, onArticleClick }: Props) {
  const router = useRouter();

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newDate = e.target.value;
    if (newDate) {
      router.push(`/daily-ca/${newDate}`);
    }
  };

  return (
    <aside className="flex flex-col gap-4">
      {/* Date header */}
      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg">📅</span>
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold">
              News Today
            </p>
            <p className="text-sm font-bold text-gray-800">
              {formatDate(date)}
            </p>
          </div>
        </div>
        <input
          type="date"
          value={date}
          onChange={handleDateChange}
          className="w-full rounded-lg border border-gray-200 px-2.5 py-1.5 text-xs text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Table of Contents */}
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="px-4 py-2.5 border-b border-gray-100">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Table of Contents
          </p>
          <p className="text-xs text-gray-400">{articles.length} articles</p>
        </div>
        <nav className="py-1.5">
          {articles.map((article, index) => {
            const isActive = article.id === activeId;
            const gsColor = GS_COLORS[article.gs_paper] ?? GS_COLORS["CSAT"];
            return (
              <button
                key={article.id}
                onClick={() => onArticleClick(article.id)}
                className={`w-full text-left px-3 py-2.5 flex items-start gap-2.5 transition-colors ${
                  isActive
                    ? "bg-blue-50 border-l-2 border-blue-500"
                    : "hover:bg-gray-50 border-l-2 border-transparent"
                }`}
              >
                {/* Index */}
                <span
                  className={`flex-shrink-0 mt-0.5 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                    isActive
                      ? "bg-blue-500 text-white"
                      : "bg-gray-100 text-gray-500"
                  }`}
                >
                  {index + 1}
                </span>
                <div className="min-w-0">
                  <p
                    className={`text-xs leading-snug line-clamp-2 ${
                      isActive ? "font-semibold text-blue-700" : "text-gray-700"
                    }`}
                  >
                    {article.title}
                  </p>
                  <div className="flex items-center gap-1.5 mt-1">
                    {article.gs_paper && (
                      <span
                        className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold ${gsColor}`}
                      >
                        {article.gs_paper}
                      </span>
                    )}
                    <span className="text-[10px] text-gray-400 truncate">
                      {article.subject_name}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}

          {articles.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-6">
              No articles yet
            </p>
          )}
        </nav>
      </div>
    </aside>
  );
}
