/**
 * @file sentry.server.config.ts
 * @description Sentry SDK initialisation for the **Node.js server** runtime.
 *
 * Covers: Server Components, Route Handlers, Server Actions, and middleware.
 * Runs in the Node.js process and has access to server-only environment vars.
 *
 * Docs: https://docs.sentry.io/platforms/javascript/guides/nextjs/
 */

import * as Sentry from "@sentry/nextjs";

Sentry.init({
    dsn: process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN,

    // ── Environment ───────────────────────────────────────────────────────────
    environment: process.env.NODE_ENV,

    // ── Performance Monitoring ────────────────────────────────────────────────
    /**
     * 10 % sampling in production keeps costs low while preserving signal.
     * 100 % in dev / staging so nothing is missed during testing.
     */
    tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,

    // ── Debug ─────────────────────────────────────────────────────────────────
    debug: false,
});
