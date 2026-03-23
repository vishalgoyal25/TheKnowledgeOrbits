/**
 * Server-side hierarchy fetcher for ISR (Incremental Static Regeneration).
 * This allows us to "bake" the navigation menu into the HTML at build time.
 */

import { HierarchySubject } from "@/lib/types";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function getHierarchyData(): Promise<HierarchySubject[]> {
  try {
    const res = await fetch(`${BACKEND_URL}/knowledge/hierarchy/`, {
      // Revalidate every 30 minutes (1800 seconds) in the background
      next: { revalidate: 1800 },
      // Important: No-cache during local development if needed, 
      // but ISR is primarily for production speed.
    });

    if (!res.ok) {
        console.warn("Hierarchy fetch failed on server, falling back to empty list.");
        return [];
    }

    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.error("ISR Hierarchy fetch error:", error);
    return [];
  }
}
