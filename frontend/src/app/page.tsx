/**
 * Home page — ISR server component wrapper.
 *
 * Fetches today's Daily CA articles at build/revalidation time (every 5 min)
 * so the HTML is baked with real content before the browser ever loads.
 * The heavy client-side logic lives in HomePageClient.
 *
 * Why two files?
 *   page.tsx must be a server component to use `next: { revalidate }`.
 *   HomePageClient needs "use client" for useSidebar / useArticles hooks.
 *   Next.js does not allow both in the same file.
 */

import type { DailyFeedResponse, DailyCaArticleList } from "@/lib/api/daily-ca";
import HomePageClient from "@/components/home/home-page-client";

// ISR: Vercel re-generates this page in the background every 5 minutes.
// Visitors always get a cached HTML page — Render cold-start never affects them.
export const revalidate = 300;

// Mirror the same base-URL logic as server-hierarchy.ts
const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default async function Page() {
  let todayArticles: DailyCaArticleList[] = [];

  try {
    const res = await fetch(`${BACKEND_URL}/daily-ca/today/`, {
      // Cache this response for 5 minutes (matches the page revalidate window).
      next: { revalidate: 300 },
      // 45 s timeout — Render free tier cold-starts can take 10–30 s.
      signal: AbortSignal.timeout(45_000),
    });

    if (res.ok) {
      const data: DailyFeedResponse = await res.json();
      todayArticles = [...data.articles].sort(
        (a, b) => a.order_on_date - b.order_on_date,
      );
    }
  } catch {
    // Network error / timeout / Render asleep — serve empty list gracefully.
    // The widget will show "No articles yet today." rather than a skeleton.
    todayArticles = [];
  }

  return <HomePageClient initialTodayArticles={todayArticles} />;
}
