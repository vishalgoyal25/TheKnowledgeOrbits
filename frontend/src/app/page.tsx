/**
 * Home page — ISR server component wrapper.
 *
 * Fetches today's Daily CA articles AND today's Daily Public Quiz in parallel
 * at build/revalidation time (every 5 min) so the HTML is baked with real
 * content before the browser ever loads. The heavy client-side logic lives in
 * HomePageClient.
 *
 * Why two files?
 *   page.tsx must be a server component to use `next: { revalidate }`.
 *   HomePageClient needs "use client" for useSidebar / useArticles hooks.
 *   Next.js does not allow both in the same file.
 *
 * Parallel ISR fetches:
 *   Both requests run concurrently via Promise.allSettled. A failure in either
 *   one does not block the other — the component receives null/[] for the
 *   failed resource and renders gracefully.
 */

import type { DailyFeedResponse, DailyCaArticleList } from "@/lib/api/daily-ca";
import type { Quiz } from "@/lib/types";
import HomePageClient from "@/components/home/home-page-client";

// ISR: Vercel re-generates this page in the background every 5 minutes.
// Visitors always get a cached HTML page — Render cold-start never affects them.
export const revalidate = 300;

// Mirror the same base-URL logic as server-hierarchy.ts
const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default async function Page() {
  let todayArticles: DailyCaArticleList[] = [];
  let todayQuiz: Quiz | null = null;

  // Parallel ISR fetches — neither blocks the other
  const [caResult, quizResult] = await Promise.allSettled([
    fetch(`${BACKEND_URL}/daily-ca/today/`, {
      // Cache this response for 5 minutes (matches the page revalidate window).
      next: { revalidate: 300 },
      // 45 s timeout — Render free tier cold-starts can take 10–30 s.
      signal: AbortSignal.timeout(45_000),
    }),
    fetch(`${BACKEND_URL}/assessment/public/daily/`, {
      next: { revalidate: 300 },
      signal: AbortSignal.timeout(45_000),
    }),
  ]);

  // Process CA articles
  if (caResult.status === "fulfilled" && caResult.value.ok) {
    try {
      const data: DailyFeedResponse = await caResult.value.json();
      todayArticles = [...data.articles].sort(
        (a, b) => a.order_on_date - b.order_on_date,
      );
    } catch {
      // JSON parse failure — serve empty list gracefully
      todayArticles = [];
    }
  }
  // else: network error / Render asleep / 404 — widget shows "No articles yet"

  // Process daily quiz
  if (quizResult.status === "fulfilled" && quizResult.value.ok) {
    try {
      todayQuiz = (await quizResult.value.json()) as Quiz;
    } catch {
      // JSON parse failure — widget shows empty state
      todayQuiz = null;
    }
  }
  // else: quiz not yet generated (404) or network error — widget shows empty state

  return (
    <HomePageClient
      initialTodayArticles={todayArticles}
      initialTodayQuiz={todayQuiz}
    />
  );
}
