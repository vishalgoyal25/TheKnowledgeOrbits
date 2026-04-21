"use client";

/**
 * P3.1 — ArticleTopBar
 * Extracted client component: back button (router.back) + share button (clipboard).
 * Receives article title as a static prop from the server component.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  title: string;
}

export function ArticleTopBar({ title }: Props) {
  const router = useRouter();
  const [copied, setCopied] = useState(false);

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard not available in all environments
    }
  };

  return (
    <div className="sticky top-0 z-20 bg-white border-b border-gray-200">
      <div className="max-w-[1400px] mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => router.back()}
            className="text-gray-400 hover:text-gray-700 flex-shrink-0 text-sm transition-colors"
          >
            ←
          </button>
          <p className="text-sm font-semibold text-gray-800 truncate hidden sm:block">
            {title}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Share button */}
          <button
            onClick={handleShare}
            title="Copy link"
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-600 border border-gray-200 rounded-lg px-3 py-1.5 transition-colors"
          >
            {copied ? (
              <>
                <span className="text-green-600">✓</span> Copied!
              </>
            ) : (
              <>
                <svg
                  className="w-3.5 h-3.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
                  />
                </svg>{" "}
                Share
              </>
            )}
          </button>
          {/* Bookmark stub */}
          <button
            title="Bookmark (coming soon)"
            className="flex items-center gap-1.5 text-xs text-gray-400 border border-gray-200 rounded-lg px-3 py-1.5 cursor-default"
          >
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
              />
            </svg>
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
