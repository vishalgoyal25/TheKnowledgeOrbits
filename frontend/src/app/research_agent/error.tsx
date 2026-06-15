"use client";

// Next.js requires error.tsx to be a Client Component.
// It receives the thrown Error and a reset() callback to re-mount the route.

import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function ResearchAgentError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // Log to console in development; in production this would go to Sentry.
  useEffect(() => {
    console.error("[ResearchAgent] Uncaught error:", error);
  }, [error]);

  return (
    <div className="mx-auto flex max-w-md flex-col items-center justify-center gap-5 px-4 py-24 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-50">
        <AlertTriangle className="h-7 w-7 text-red-500" />
      </div>

      <div className="space-y-1.5">
        <h2 className="text-lg font-semibold text-gray-800">
          Something went wrong
        </h2>
        <p className="text-sm text-gray-500">
          The research agent encountered an unexpected error.
          {process.env.NODE_ENV === "development" && error.message && (
            <span className="mt-1 block font-mono text-xs text-red-400">
              {error.message}
            </span>
          )}
        </p>
      </div>

      <button
        type="button"
        onClick={reset}
        className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 active:bg-blue-800 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
      >
        <RefreshCw className="h-3.5 w-3.5" />
        Try Again
      </button>
    </div>
  );
}
