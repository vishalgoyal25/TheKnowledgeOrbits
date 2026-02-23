/**
 * @file sentry.client.config.ts
 * @description Sentry SDK initialisation for the **browser** runtime.
 *
 * This file is automatically imported by Next.js before any application code
 * runs on the client side. It must NOT import any server-only modules.
 *
 * Docs: https://docs.sentry.io/platforms/javascript/guides/nextjs/
 */

import * as Sentry from "@sentry/nextjs";

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

Sentry.init({
  dsn: SENTRY_DSN,

  // ── Environment ───────────────────────────────────────────────────────────
  environment: process.env.NODE_ENV,

  // ── Performance Monitoring ────────────────────────────────────────────────
  /**
   * Capture 10 % of transactions in production for performance monitoring.
   * Set to 1.0 during development for full visibility.
   */
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,

  // ── Session Replay ────────────────────────────────────────────────────────
  /**
   * Replay 5 % of all sessions; 100 % of sessions where an error occurred.
   * Remove or reduce if you hit Sentry quota limits.
   */
  replaysSessionSampleRate: 0.05,
  replaysOnErrorSampleRate: 1.0,

  integrations: [
    Sentry.replayIntegration({
      // Mask all text content and input values for privacy
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],

  // ── Debug ─────────────────────────────────────────────────────────────────
  /** Set to true locally to see every Sentry event logged to the console. */
  debug: false,

  // ── Ignored Errors ────────────────────────────────────────────────────────
  /**
   * Filter out low-signal errors that would inflate your Sentry quota.
   * Add more patterns here as they are identified.
   */
  ignoreErrors: [
    // Browser extensions
    "ResizeObserver loop limit exceeded",
    "ResizeObserver loop completed with undelivered notifications",
    // Network noise
    "Network Error",
    "Failed to fetch",
    "Load failed",
    // Next.js router cancelled navigations
    "Abort fetching component for route",
  ],
});
