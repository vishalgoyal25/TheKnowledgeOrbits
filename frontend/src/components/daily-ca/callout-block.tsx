"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * CalloutBlock — renders :::callout\n...\n::: blocks from CA article markdown.
 * These are "Did You Know?" style sidebars injected by the LLM.
 * Uses ReactMarkdown so inline links, bold, etc. render correctly.
 */

interface Props {
  content: string;
}

export function CalloutBlock({ content }: Props) {
  return (
    <div className="my-4 flex gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
      <span className="mt-0.5 flex-shrink-0 text-lg" aria-hidden="true">
        💡
      </span>
      <div className="text-sm leading-relaxed text-amber-900 [&_p]:mb-1 [&_p:last-child]:mb-0">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            p: ({ children }) => (
              <p className="text-sm leading-relaxed text-amber-900">
                {children}
              </p>
            ),
            strong: ({ children }) => (
              <strong className="font-semibold text-amber-950">
                {children}
              </strong>
            ),
            a: ({ href, children }) => (
              <a
                href={href}
                className="font-medium text-blue-700 underline underline-offset-2 hover:text-blue-900 transition-colors"
              >
                {children}
              </a>
            ),
          }}
        >
          {content.trim()}
        </ReactMarkdown>
      </div>
    </div>
  );
}
