/**
 * Server-side hierarchy fetcher for ISR (Incremental Static Regeneration).
 * This allows us to "bake" the navigation menu into the HTML at build time.
 */

import { HierarchySubject } from "@/lib/types";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function getHierarchyData(): Promise<HierarchySubject[]> {
  try {
    const res = await fetch(`${BACKEND_URL}/knowledge/hierarchy/`, {
      // Revalidate every 30 minutes (1800 seconds) in the background.
      next: { revalidate: 1800 },
      // 45 s timeout — Render free tier cold-starts can take 10–30 s.
      // Without this, the default Node.js socket timeout (~30 s) races
      // unpredictably; an explicit 45 s gives Render time to wake up.
      signal: AbortSignal.timeout(45_000),
    });

    if (!res.ok) {
      // Non-ok response (e.g. 500 from Render cold start) — return empty list
      // gracefully. layout.tsx will render the header with no subjects; the
      // client staleness guard will re-fetch once the server warms up.
      return [];
    }

    const data = await res.json();

    // If the data is an array of programs with nested subjects, flatten it.
    if (Array.isArray(data) && data[0]?.subjects) {
      return data.flatMap((program) => program.subjects || []);
    }

    return Array.isArray(data) ? data : [];
  } catch {
    // Network error / timeout / Render asleep — fail silently.
    // The client staleness guard (header.tsx) will re-fetch on next navigation.
    return [];
  }
}
