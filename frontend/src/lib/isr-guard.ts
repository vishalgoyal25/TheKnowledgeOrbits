import { isAxiosError } from "axios";

/**
 * Build-time guard for detail pages that prerender.
 *
 * The problem this exists for
 * ───────────────────────────
 * Graceful degradation is correct for a live request and wrong at build time.
 * A detail page that catches a failed fetch and renders "something went wrong"
 * has that fallback PRERENDERED AND CACHED, then served to every visitor for
 * the life of the cache entry. The 2026-09-04 build did exactly this: it went
 * green while detail fetches were erroring, and /current-affairs/[id] would
 * have baked a spinner into static HTML (FEATURES_GROWTH_STACK §5A.4a).
 *
 * List pages already guard this way inline (articles, current-affairs, topics).
 * This centralises the rule because the interesting part is NOT "throw on
 * error" — it is the distinction below, which is easy to get subtly wrong in
 * each copy.
 *
 * Outage vs data
 * ──────────────
 *   no response / 5xx  → the API is unreachable or broken. Abort the build
 *                        rather than cache an error page.
 *   4xx (incl. 404)    → the API answered. The row is gone or the request was
 *                        rejected. That is data, not an outage: one missing
 *                        item must never fail a 238-page build. The caller
 *                        renders notFound() instead.
 *
 * A non-Axios error is a genuine bug in our own render path. It is rethrown
 * unchanged, never relabelled as "API unreachable" — disguising a TypeError as
 * an outage would send the next person hunting the wrong problem.
 */
export function abortIfApiUnreachable(error: unknown, label: string): void {
  // CI builds run with no backend on purpose (see wait-for-backend.js).
  if (process.env.SKIP_BACKEND_WAIT === "true") {
    return;
  }

  if (!isAxiosError(error)) {
    throw error;
  }

  const status = error.response?.status;

  if (status !== undefined && status < 500) {
    return;
  }

  throw new Error(
    `${label} unreachable during ISR build - Aborting to protect cache`,
  );
}
