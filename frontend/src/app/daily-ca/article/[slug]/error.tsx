"use client";

/**
 * Error boundary for the article detail route.
 *
 * Catches any client-side crash (hydration failure, component throw, etc.)
 * and shows a recoverable UI instead of a blank white page.
 *
 * Next.js requires this to be a Client Component ("use client").
 */

import Link from "next/link";

export default function ArticleError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="text-5xl mb-4">⚠️</div>
        <h1 className="text-xl font-bold text-gray-800 mb-2">
          Couldn&apos;t load this article
        </h1>
        <p className="text-sm text-gray-500 mb-6">
          Something went wrong while loading the article. Try refreshing, or
          browse other articles in the Daily CA feed.
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={reset}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            Try again
          </button>
          <Link
            href="/daily-ca"
            className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors"
          >
            Back to feed
          </Link>
        </div>
      </div>
    </div>
  );
}
