"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  getTodayArticles,
  getArticlesByDate,
  DailyCaArticleList,
} from "@/lib/api/daily-ca";

// ── GS colour map ─────────────────────────────────────────────────────────────

const GS_CHIP: Record<string, { bg: string; text: string; label: string }> = {
  GS1: { bg: "bg-purple-100", text: "text-purple-700", label: "GS1" },
  GS2: { bg: "bg-blue-100", text: "text-blue-700", label: "GS2" },
  GS3: { bg: "bg-emerald-100", text: "text-emerald-700", label: "GS3" },
  GS4: { bg: "bg-orange-100", text: "text-orange-700", label: "GS4" },
  CSAT: { bg: "bg-gray-100", text: "text-gray-600", label: "CSAT" },
};

// ── Date helpers ──────────────────────────────────────────────────────────────

function toISODate(d: Date): string {
  return d.toISOString().split("T")[0];
}

function todayISO(): string {
  return toISODate(new Date());
}

/** Returns last N days as ISO strings, newest first (index 0 = today). */
function lastNDays(n: number): string[] {
  return Array.from({ length: n }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - i);
    return toISODate(d);
  });
}

function chipLabel(iso: string, todayStr: string): string {
  if (iso === todayStr) return "Today";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function formatHeading(iso: string, todayStr: string): string {
  if (iso === todayStr) return "Today's";
  const d = new Date(iso + "T00:00:00");
  return (
    d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }) + "'s"
  );
}

function estimateReadTime(title: string, context: string): number {
  return Math.max(
    1,
    Math.round((title + " " + context).split(/\s+/).length / 200) + 1,
  );
}

// ── Mini Card ─────────────────────────────────────────────────────────────────

function MiniCard({
  article,
  index,
}: {
  article: DailyCaArticleList;
  index: number;
}) {
  const gs = GS_CHIP[article.gs_paper] ?? GS_CHIP["CSAT"];
  const readMin = estimateReadTime(article.title, article.news_context ?? "");

  return (
    <Link
      href={`/daily-ca/article/${article.slug}`}
      className="group relative flex flex-col rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden
                 hover:border-blue-300 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200"
    >
      {/* Hero image thumbnail */}
      {article.hero_image_url && (
        <div className="relative w-full h-32 flex-shrink-0">
          <Image
            src={article.hero_image_url}
            alt={article.title}
            fill
            className="object-cover"
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 250px"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/20 via-transparent to-transparent" />
        </div>
      )}

      {/* Card content */}
      <div className="flex flex-col gap-2.5 p-4">
        {/* Number badge + GS chip row */}
        <div className="flex items-center justify-between">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-900 text-[10px] font-bold text-white flex-shrink-0">
            {index + 1}
          </span>
          <div className="flex items-center gap-1.5">
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${gs.bg} ${gs.text}`}
            >
              {gs.label}
            </span>
            <span className="text-[10px] text-slate-400 font-medium truncate max-w-[80px]">
              {article.subject_name}
            </span>
          </div>
        </div>

        {/* Title */}
        <p className="text-sm font-bold text-blue-900 leading-snug line-clamp-2 group-hover:text-blue-700 transition-colors">
          {article.title}
        </p>

        {/* News context */}
        {article.news_context && (
          <p className="text-xs text-slate-500 italic leading-relaxed line-clamp-1">
            {article.news_context}
          </p>
        )}

        {/* Footer */}
        <div className="mt-auto flex items-center justify-between pt-1">
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">
            ⏱ {readMin} min read
          </span>
          <span className="text-[10px] font-semibold text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity">
            Read →
          </span>
        </div>
      </div>
    </Link>
  );
}

// ── Skeleton card ─────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="flex flex-col gap-2.5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm animate-pulse">
      <div className="flex items-center justify-between">
        <div className="h-6 w-6 rounded-full bg-slate-200" />
        <div className="h-4 w-16 rounded-full bg-slate-200" />
      </div>
      <div className="h-4 w-full rounded bg-slate-200" />
      <div className="h-4 w-3/4 rounded bg-slate-200" />
      <div className="h-3 w-2/3 rounded bg-slate-100" />
      <div className="h-4 w-16 rounded-full bg-slate-100 mt-1" />
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ date }: { date: string }) {
  return (
    <div className="col-span-full flex flex-col items-center justify-center py-14 gap-3">
      <span className="text-4xl">📭</span>
      <p className="text-sm font-semibold text-slate-600">
        No articles for {date}
      </p>
      <p className="text-xs text-slate-400">
        Articles are generated daily — try a different date or check back later.
      </p>
    </div>
  );
}

// ── Date chip strip ───────────────────────────────────────────────────────────

interface ChipStripProps {
  selectedDate: string;
  todayStr: string;
  onSelect: (iso: string) => void;
}

function DateChipStrip({ selectedDate, todayStr, onSelect }: ChipStripProps) {
  const days = lastNDays(7);
  const calendarRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {days.map((iso) => {
        const isSelected = iso === selectedDate;
        const isToday = iso === todayStr;
        return (
          <button
            key={iso}
            onClick={() => onSelect(iso)}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-all duration-150 border ${
              isSelected
                ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                : isToday
                  ? "bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100"
                  : "bg-white text-slate-600 border-slate-200 hover:border-blue-300 hover:text-blue-700"
            }`}
          >
            {chipLabel(iso, todayStr)}
          </button>
        );
      })}

      {/* Calendar icon — opens native date picker for dates older than 7 days */}
      <div className="relative">
        <button
          onClick={() => calendarRef.current?.showPicker?.()}
          title="Pick an older date"
          className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold border transition-all duration-150 ${
            !days.includes(selectedDate)
              ? "bg-blue-600 text-white border-blue-600 shadow-sm"
              : "bg-white text-slate-500 border-slate-200 hover:border-blue-300 hover:text-blue-700"
          }`}
        >
          <svg
            className="h-3.5 w-3.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
            />
          </svg>
          {!days.includes(selectedDate)
            ? chipLabel(selectedDate, todayStr)
            : "Older"}
        </button>
        <input
          ref={calendarRef}
          type="date"
          value={selectedDate}
          max={todayStr}
          onChange={(e) => {
            if (e.target.value) onSelect(e.target.value);
          }}
          className="absolute inset-0 opacity-0 w-full cursor-pointer"
          aria-label="Pick a date"
        />
      </div>
    </div>
  );
}

// ── Main Widget ───────────────────────────────────────────────────────────────

// P3.2 — accepts today's articles from the homepage so we don't double-fetch.
// initialArticles: undefined = parent still loading; [] or [...] = data ready.
// When selectedDate changes to a non-today date, self-fetch runs as normal.
export function DailyCaTeaserWidget({
  initialArticles,
}: {
  initialArticles?: DailyCaArticleList[];
}) {
  const TODAY = todayISO();

  const [selectedDate, setSelectedDate] = useState<string>(TODAY);
  const [articles, setArticles] = useState<DailyCaArticleList[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasEverLoaded, setHasEverLoaded] = useState(false);

  const fetchArticles = useCallback(
    async (iso: string) => {
      setLoading(true);
      try {
        const res =
          iso === TODAY
            ? await getTodayArticles()
            : await getArticlesByDate(iso);
        setArticles(res.articles.slice(0, 10));
        setHasEverLoaded(true);
      } catch {
        setArticles([]);
        setHasEverLoaded(true);
      } finally {
        setLoading(false);
      }
    },
    [TODAY],
  );

  useEffect(() => {
    if (selectedDate === TODAY) {
      // P3.2 — today's data comes from parent (HomePage fetched it once).
      // Wait for initialArticles to become non-undefined; don't self-fetch.
      if (initialArticles !== undefined) {
        setArticles(initialArticles.slice(0, 10));
        setLoading(false);
        setHasEverLoaded(true);
      }
      // else: still undefined (parent loading) — stay in loading state
      return;
    }
    // Non-today dates: self-fetch as normal
    fetchArticles(selectedDate);
  }, [fetchArticles, selectedDate, TODAY, initialArticles]);

  const handleDateSelect = (iso: string) => {
    if (iso === selectedDate) return;
    setSelectedDate(iso);
  };

  // Hide section entirely only if initial load failed with no articles
  if (!loading && !hasEverLoaded) return null;

  const heading = formatHeading(selectedDate, TODAY);
  const count = articles.length;
  const isToday = selectedDate === TODAY;

  return (
    <section className="border-b border-slate-100 bg-gradient-to-b from-slate-50 to-white py-14 px-4">
      <div className="mx-auto max-w-7xl">
        {/* ── Header ── */}
        <div className="mb-6 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div className="min-w-0">
            {/* Eyebrow */}
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
              <span className="text-xs font-semibold text-blue-600 uppercase tracking-wide">
                {isToday ? "Live Daily Updates" : "Archive"}
              </span>
            </div>

            {/* Dynamic heading */}
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
              {heading}{" "}
              <span className="bg-gradient-to-r from-blue-600 to-cyan-500 bg-clip-text text-transparent">
                Current Affairs
              </span>
            </h2>

            {/* Subtitle */}
            <p className="mt-1 text-sm text-slate-500 h-5">
              {loading ? (
                <span className="inline-block h-4 w-36 rounded bg-slate-200 animate-pulse" />
              ) : (
                <>
                  <span className="font-semibold text-slate-700">
                    {count} article{count !== 1 ? "s" : ""}
                  </span>
                  {isToday ? " · Updated daily" : " · Historical archive"}
                </>
              )}
            </p>
          </div>

          {/* Desktop CTA */}
          <Link
            href={isToday ? "/daily-ca" : `/daily-ca/${selectedDate}`}
            className="hidden sm:inline-flex items-center gap-2 rounded-xl border border-blue-200 bg-white px-5 py-2.5
                       text-sm font-semibold text-blue-700 shadow-sm hover:bg-blue-50 hover:border-blue-300
                       hover:shadow-md transition-all duration-200 flex-shrink-0 self-start mt-1"
          >
            Open full page
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </Link>
        </div>

        {/* ── Date chip strip ── */}
        <div className="mb-6">
          <DateChipStrip
            selectedDate={selectedDate}
            todayStr={TODAY}
            onSelect={handleDateSelect}
          />
        </div>

        {/* ── Grid ── */}
        <div
          className={`grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 transition-opacity duration-200 ${
            loading ? "opacity-50 pointer-events-none" : "opacity-100"
          }`}
        >
          {loading ? (
            Array.from({ length: 10 }).map((_, i) => <SkeletonCard key={i} />)
          ) : articles.length === 0 ? (
            <EmptyState date={selectedDate} />
          ) : (
            articles.map((a, i) => (
              <MiniCard key={a.id} article={a} index={i} />
            ))
          )}
        </div>

        {/* ── CTA strip ── */}
        {!loading && articles.length > 0 && (
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href={isToday ? "/daily-ca" : `/daily-ca/${selectedDate}`}
              className="group inline-flex items-center gap-3 rounded-2xl bg-gradient-to-r from-blue-600 to-cyan-500
                         px-8 py-3.5 text-sm font-bold text-white shadow-lg hover:shadow-xl
                         hover:from-blue-700 hover:to-cyan-600 active:scale-[0.98] transition-all duration-200"
            >
              Read All {heading} Current Affairs
              <svg
                className="h-4 w-4 group-hover:translate-x-0.5 transition-transform"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </Link>
          </div>
        )}
      </div>
    </section>
  );
}
