"use client";

import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ConceptDetail } from "@/lib/api/tags";
import { ConceptStubCard } from "./concept-stub-card";

/**
 * ConceptDetail — full layout for /concepts/[slug]/.
 *
 * Two states:
 *  - is_content_ready=false → stub card + brief description + linked articles list
 *  - is_content_ready=true  → full body_md rendered + linked articles below
 *
 * Sidebar: usage_count, related concept pages (from linked articles), back link.
 */

// ── Markdown normaliser ───────────────────────────────────────────────────────
// LLMs sometimes return headings with only a single \n before them.
// ReactMarkdown requires a blank line (\n\n) to treat ## as a block heading.
// Without this, headings render as inline text inside the preceding paragraph.

function normalizeConceptBody(md: string): string {
  if (!md) return "";
  return (
    md
      // Normalise Windows line endings first
      .replace(/\r\n/g, "\n")
      // Ensure blank line BEFORE any ## or ### heading
      // e.g. "...sentence.\n## Heading" → "...sentence.\n\n## Heading"
      .replace(/([^\n])\n(#{1,3} )/g, "$1\n\n$2")
      // Ensure blank line AFTER any heading before body text begins
      // e.g. "## Heading\nFirst sentence" → "## Heading\n\nFirst sentence"
      .replace(/(#{1,3} [^\n]+)\n([^#\n])/g, "$1\n\n$2")
      // Collapse 3+ blank lines to 2
      .replace(/\n{3,}/g, "\n\n")
      .trim()
  );
}

// ── Markdown components (concept body) ───────────────────────────────────────

const mdComponents = {
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="text-xl font-bold text-gray-900 mt-8 mb-3 pb-2 border-b-2 border-purple-100 tracking-tight leading-snug">
      {children}
    </h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="text-lg font-semibold text-gray-800 mt-6 mb-2 leading-snug">
      {children}
    </h3>
  ),
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="text-base leading-7 text-gray-700 mb-4">{children}</p>
  ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="my-4 space-y-2 pl-2">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="my-4 space-y-2 pl-5 list-decimal">{children}</ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="text-base text-gray-700 leading-7 flex gap-2.5">
      <span className="flex-shrink-0 text-purple-400 font-bold mt-0.5">•</span>
      <span>{children}</span>
    </li>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-gray-900">{children}</strong>
  ),
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a
      href={href}
      className="text-base text-blue-600 font-medium underline underline-offset-2 hover:text-blue-800 transition-colors"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="my-5 border-l-4 border-purple-300 bg-purple-50/50 pl-4 pr-3 py-3 rounded-r-xl text-base italic leading-7 text-gray-600">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-6 border-t border-gray-200" />,
  code: ({ children }: { children?: React.ReactNode }) => (
    <code className="text-sm bg-gray-100 rounded px-1.5 py-0.5 font-mono text-gray-800">
      {children}
    </code>
  ),
};

// ── Linked Articles list ──────────────────────────────────────────────────────

function LinkedArticlesList({
  articles,
}: {
  articles: { title: string; slug: string }[];
}) {
  if (articles.length === 0) return null;

  return (
    <div className="mt-8 pt-6 border-t border-gray-100">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
        Articles that reference this concept
      </h2>
      <div className="space-y-2">
        {articles.map((a) => (
          <Link
            key={a.slug}
            href={`/daily-ca/article/${a.slug}`}
            className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-4 py-3 hover:border-blue-300 hover:shadow-sm transition-all group"
          >
            <p className="text-sm text-gray-800 leading-snug group-hover:text-blue-700 transition-colors line-clamp-2 pr-4">
              {a.title}
            </p>
            <span className="flex-shrink-0 text-xs font-semibold text-blue-500 group-hover:text-blue-700">
              Read →
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

function ConceptSidebar({ concept }: { concept: ConceptDetail }) {
  const createdYear = concept.created_at
    ? new Date(concept.created_at).getFullYear()
    : null;

  return (
    <aside className="space-y-4">
      {/* Back */}
      <Link
        href="/daily-ca"
        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-600 transition-colors"
      >
        ← Daily CA Feed
      </Link>

      {/* Stats card */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Concept Info
        </p>

        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Status</span>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
              concept.is_content_ready
                ? "bg-green-100 text-green-700"
                : "bg-amber-100 text-amber-700"
            }`}
          >
            {concept.is_content_ready ? "Full Article" : "Stub"}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Referenced in</span>
          <span className="text-xs font-semibold text-gray-800">
            {concept.usage_count} article{concept.usage_count !== 1 ? "s" : ""}
          </span>
        </div>

        {createdYear && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">First seen</span>
            <span className="text-xs font-semibold text-gray-800">
              {createdYear}
            </span>
          </div>
        )}
      </div>

      {/* Recent linked articles (sidebar list) */}
      {concept.linked_articles.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Referenced in
            </p>
          </div>
          <div className="divide-y divide-gray-50">
            {concept.linked_articles.map((a) => (
              <Link
                key={a.slug}
                href={`/daily-ca/article/${a.slug}`}
                className="block px-4 py-2.5 text-xs text-gray-700 hover:bg-gray-50 hover:text-blue-700 transition-colors line-clamp-2"
              >
                {a.title}
              </Link>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

interface Props {
  concept: ConceptDetail;
}

export function ConceptDetailComponent({ concept }: Props) {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Page header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-[1200px] mx-auto px-4 py-7">
          <div className="flex items-start gap-3 mb-2">
            <span className="text-2xl mt-0.5" aria-hidden="true">
              🔷
            </span>
            <div>
              <p className="text-xs font-semibold text-purple-600 uppercase tracking-wide mb-1">
                Concept Page
              </p>
              <h1 className="text-xl font-bold text-gray-900 leading-snug">
                {concept.name}
              </h1>
            </div>
          </div>
        </div>
      </div>

      {/* Layout */}
      <div className="max-w-[1200px] mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
          {/* Main */}
          <main className="space-y-4">
            {/* Stub state */}
            {!concept.is_content_ready && (
              <ConceptStubCard
                name={concept.name}
                briefDescription={concept.brief_description}
              />
            )}

            {/* Full content state */}
            {concept.is_content_ready && concept.body && (
              <div className="rounded-2xl border border-gray-200 bg-white px-6 py-6">
                {/* Always show brief description at top as a quick summary */}
                {concept.brief_description && (
                  <div className="mb-5 pb-4 border-b border-gray-100">
                    <p className="text-sm text-gray-600 leading-relaxed italic">
                      {concept.brief_description}
                    </p>
                  </div>
                )}
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={mdComponents}
                >
                  {normalizeConceptBody(concept.body)}
                </ReactMarkdown>
              </div>
            )}

            {/* Linked articles (shown in both states) */}
            <div className="rounded-2xl border border-gray-200 bg-white px-6 py-6">
              {concept.linked_articles.length > 0 ? (
                <LinkedArticlesList articles={concept.linked_articles} />
              ) : (
                <div className="text-center py-8">
                  <p className="text-sm text-gray-400">
                    No published articles reference this concept yet.
                  </p>
                </div>
              )}
            </div>
          </main>

          {/* Sidebar */}
          <div className="hidden lg:block">
            <div className="sticky top-6">
              <ConceptSidebar concept={concept} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
