/**
 * Not-found boundary for the article detail route.
 *
 * Rendered when fetchArticle() returns null (404 from backend) and
 * the page component calls notFound(). Replaces the default Next.js
 * "404 | This page could not be found." with a branded UI.
 */

import Link from "next/link";

export default function ArticleNotFound() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="text-5xl mb-4">📄</div>
        <h1 className="text-xl font-bold text-gray-800 mb-2">
          Article not found
        </h1>
        <p className="text-sm text-gray-500 mb-6">
          This article doesn&apos;t exist or hasn&apos;t been published yet. It
          may still be generating — check back in a few minutes.
        </p>
        <Link
          href="/daily-ca"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          ← Browse Daily CA
        </Link>
      </div>
    </div>
  );
}
