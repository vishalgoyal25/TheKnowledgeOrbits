/**
 * @file next.config.ts
 * @description Next.js configuration — wrapped with Sentry for error & performance monitoring.
 *
 * Docs:
 *  - https://nextjs.org/docs/pages/api-reference/next-config-js
 *  - https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/
 */

import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
  },
};

export default withSentryConfig(nextConfig, {
  // ── Source Maps ────────────────────────────────────────────────────────────
  /**
   * Your Sentry organisation and project slugs.
   * Set these in .env.local or CI secrets — they are used only at build time.
   */
  org: process.env.SENTRY_ORG || "",
  project: process.env.SENTRY_PROJECT || "",

  // ── Auth Token ────────────────────────────────────────────────────────────
  /**
   * Auth token for uploading source maps to Sentry.
   * Create one at: https://sentry.io/settings/account/api/auth-tokens/
   * Required scopes: project:releases, org:read
   */
  authToken: process.env.SENTRY_AUTH_TOKEN,

  // ── Silent Build ──────────────────────────────────────────────────────────
  /** Suppress noisy Sentry CLI output during builds. */
  silent: !process.env.CI,

  // ── Source Map Upload ─────────────────────────────────────────────────────
  /**
   * Upload source maps so Sentry shows original TypeScript in stack traces.
   * .map files are automatically deleted from the public build output.
   */
  sourcemaps: {
    disable: false,
    deleteSourcemapsAfterUpload: true,
  },

  // ── Tunnel ────────────────────────────────────────────────────────────────
  /**
   * Routes Sentry requests through your own domain to bypass ad blockers.
   * Creates a /monitoring route in your Next.js app.
   */
  tunnelRoute: "/monitoring",

  // ── Tree-Shaking ──────────────────────────────────────────────────────────
  /** Discard Sentry logger statements from the production client bundle. */
  disableLogger: true,

  // ── React Component Names ─────────────────────────────────────────────────
  /**
   * Automatically annotate React components so Sentry error reports show
   * the component display name instead of anonymous function references.
   */
  reactComponentAnnotation: {
    enabled: true,
  },
});
