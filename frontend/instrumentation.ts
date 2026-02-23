/**
 * @file instrumentation.ts
 * @description Next.js Instrumentation Hook.
 *
 * This is the **official** way to initialise server-side observability tools
 * in Next.js 14+. It is called once when the server starts and correctly
 * separates Node.js vs Edge runtime configs.
 *
 * Docs: https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
 */

export async function register() {
    if (process.env.NEXT_RUNTIME === "nodejs") {
        await import("./sentry.server.config");
    }

    if (process.env.NEXT_RUNTIME === "edge") {
        await import("./sentry.edge.config");
    }
}
