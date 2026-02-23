/**
 * @file sentry.edge.config.ts
 * @description Sentry SDK initialisation for the **Edge runtime**.
 *
 * Covers: Next.js middleware running at the CDN edge.
 * NOTE: Edge runtime has no Node.js APIs — keep this config minimal.
 *
 * Docs: https://docs.sentry.io/platforms/javascript/guides/nextjs/
 */

import * as Sentry from "@sentry/nextjs";

Sentry.init({
    dsn: process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN,

    environment: process.env.NODE_ENV,

    // Edge transactions are cheap — sample all of them
    tracesSampleRate: 1.0,

    debug: false,
});
