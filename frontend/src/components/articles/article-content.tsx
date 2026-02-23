/**
 * Article content renderer — parses markdown-like content into styled HTML
 */

"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Props for the ArticleContent component.
 */
interface ArticleContentProps {
  /** Raw markdown string to be rendered. */
  content: string;
}

/**
 * ArticleContent - Renders markdown content with custom Tailwind-styled HTML components.
 * Supports GFM (GitHub Flavored Markdown) and provides a clean, readable layout for articles.
 */
export default function ArticleContent({ content }: ArticleContentProps) {
  return (
    <article className="prose prose-lg max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ ...props }) => (
            <h1
              className="text-3xl font-bold mt-8 mb-4 text-slate-900"
              {...props}
            />
          ),
          h2: ({ ...props }) => (
            <h2
              className="text-2xl font-bold mt-6 mb-3 text-slate-800"
              {...props}
            />
          ),
          h3: ({ ...props }) => (
            <h3
              className="text-xl font-bold mt-4 mb-2 text-slate-800"
              {...props}
            />
          ),
          p: ({ ...props }) => (
            <p className="mb-4 leading-relaxed text-slate-700" {...props} />
          ),
          ul: ({ ...props }) => (
            <ul
              className="list-disc pl-6 mb-4 space-y-2 text-slate-700"
              {...props}
            />
          ),
          ol: ({ ...props }) => (
            <ol
              className="list-decimal pl-6 mb-4 space-y-2 text-slate-700"
              {...props}
            />
          ),
          blockquote: ({ ...props }) => (
            <blockquote
              className="border-l-4 border-blue-200 pl-4 italic my-4 text-slate-600 bg-slate-50 py-2 rounded-r"
              {...props}
            />
          ),
          code: ({
            inline,
            ...props
          }: { inline?: boolean } & React.HTMLAttributes<HTMLElement>) =>
            inline ? (
              <code
                className="bg-slate-100 px-1 py-0.5 rounded text-sm font-mono text-blue-600"
                {...props}
              />
            ) : (
              <code
                className="block bg-slate-900 text-slate-100 p-4 rounded-lg my-4 text-sm font-mono overflow-x-auto shadow-inner"
                {...props}
              />
            ),
        }}
      >
        {content}
      </ReactMarkdown>
    </article>
  );
}
