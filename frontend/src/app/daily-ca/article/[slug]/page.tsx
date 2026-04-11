"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getArticleDetail, DailyCaArticleDetail } from "@/lib/api/daily-ca";
import { InSummaryBox } from "@/components/daily-ca/in-summary-box";
import { CalloutBlock } from "@/components/daily-ca/callout-block";
import { TagChips } from "@/components/daily-ca/tag-chips";
import { SourceAccordion } from "@/components/daily-ca/source-accordion";
import { RightPanel } from "@/components/daily-ca/right-panel";
import { ConceptCard } from "@/components/daily-ca/concept-card";

// ── Types ─────────────────────────────────────────────────────────────────────

type Part =
  | { type: "text"; content: string }
  | { type: "callout"; content: string };

function splitCallouts(md: string): Part[] {
  const parts: Part[] = [];
  const regex = /:::callout\n([\s\S]*?)\n:::/g;
  let last = 0;
  let m: RegExpExecArray | null;
  // eslint-disable-next-line no-cond-assign
  while ((m = regex.exec(md)) !== null) {
    if (m.index > last)
      parts.push({ type: "text", content: md.slice(last, m.index) });
    parts.push({ type: "callout", content: m[1] });
    last = m.index + m[0].length;
  }
  if (last < md.length) parts.push({ type: "text", content: md.slice(last) });
  return parts;
}

interface Heading {
  text: string;
  id: string;
}

function extractHeadings(md: string): Heading[] {
  return md
    .split("\n")
    .filter((l) => l.startsWith("## "))
    .map((l) => {
      const text = l.replace(/^##\s+/, "").trim();
      const id =
        "h-" +
        text
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-|-$/g, "");
      return { text, id };
    });
}

function slugToId(text: string): string {
  return (
    "h-" +
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
  );
}

// ── GS badge ──────────────────────────────────────────────────────────────────

const GS_COLORS: Record<string, string> = {
  GS1: "bg-purple-100 text-purple-700 border-purple-200",
  GS2: "bg-blue-100 text-blue-700 border-blue-200",
  GS3: "bg-green-100 text-green-700 border-green-200",
  GS4: "bg-orange-100 text-orange-700 border-orange-200",
  CSAT: "bg-gray-100 text-gray-600 border-gray-200",
};

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function estimateReadTime(md: string): number {
  return Math.max(1, Math.round(md.split(/\s+/).length / 200));
}

// ── Custom markdown components with heading IDs for scroll-spy ────────────────

function makeMarkdownComponents(activeHeadingId: string) {
  return {
    h2: ({ children }: { children?: React.ReactNode }) => {
      const text =
        typeof children === "string" ? children : String(children ?? "");
      const id = slugToId(text);
      return (
        <h2
          id={id}
          className={`text-base font-bold mt-6 mb-2 pb-1.5 border-b scroll-mt-20 transition-colors ${
            activeHeadingId === id
              ? "text-blue-700 border-blue-200"
              : "text-gray-900 border-gray-100"
          }`}
        >
          {children}
        </h2>
      );
    },
    h3: ({ children }: { children?: React.ReactNode }) => (
      <h3 className="text-sm font-semibold text-gray-800 mt-4 mb-1.5">
        {children}
      </h3>
    ),
    p: ({ children }: { children?: React.ReactNode }) => (
      <p className="text-sm leading-relaxed text-gray-700 mb-3">{children}</p>
    ),
    ul: ({ children }: { children?: React.ReactNode }) => (
      <ul className="my-3 space-y-1 pl-4">{children}</ul>
    ),
    ol: ({ children }: { children?: React.ReactNode }) => (
      <ol className="my-3 space-y-1 pl-4 list-decimal">{children}</ol>
    ),
    li: ({ children }: { children?: React.ReactNode }) => (
      <li className="text-sm text-gray-700 leading-relaxed flex gap-2">
        <span className="flex-shrink-0 text-blue-400 mt-1.5">•</span>
        <span>{children}</span>
      </li>
    ),
    strong: ({ children }: { children?: React.ReactNode }) => (
      <strong className="font-semibold text-gray-900">{children}</strong>
    ),
    a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
      <a
        href={href}
        className="text-blue-600 underline underline-offset-2 hover:text-blue-800 transition-colors"
      >
        {children}
      </a>
    ),
    blockquote: ({ children }: { children?: React.ReactNode }) => (
      <blockquote className="my-3 border-l-4 border-blue-300 pl-4 text-sm text-gray-600 italic">
        {children}
      </blockquote>
    ),
    table: ({ children }: { children?: React.ReactNode }) => (
      <div className="overflow-x-auto my-3">
        <table className="min-w-full text-sm border-collapse border border-gray-200 rounded-lg">
          {children}
        </table>
      </div>
    ),
    th: ({ children }: { children?: React.ReactNode }) => (
      <th className="bg-gray-50 px-3 py-2 text-left text-xs font-semibold text-gray-600 border border-gray-200">
        {children}
      </th>
    ),
    td: ({ children }: { children?: React.ReactNode }) => (
      <td className="px-3 py-2 text-xs text-gray-700 border border-gray-100">
        {children}
      </td>
    ),
  };
}

// ── Section ToC (left panel for single article) ───────────────────────────────

function SectionToC({
  headings,
  activeId,
  onHeadingClick,
}: {
  headings: Heading[];
  activeId: string;
  onHeadingClick: (id: string) => void;
}) {
  return (
    <aside className="flex flex-col gap-4">
      {/* Back link */}
      <Link
        href="/daily-ca"
        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-600 transition-colors"
      >
        ← Back to Feed
      </Link>

      {headings.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              In this Article
            </p>
          </div>
          <nav className="py-1.5">
            {headings.map((h) => (
              <button
                key={h.id}
                onClick={() => onHeadingClick(h.id)}
                className={`w-full text-left px-4 py-2 text-xs leading-snug transition-colors border-l-2 ${
                  activeId === h.id
                    ? "border-blue-500 bg-blue-50 text-blue-700 font-medium"
                    : "border-transparent text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
              >
                {h.text}
              </button>
            ))}
          </nav>
        </div>
      )}
    </aside>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ArticleDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();

  const [article, setArticle] = useState<DailyCaArticleDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeHeadingId, setActiveHeadingId] = useState("");
  const [copied, setCopied] = useState(false);

  const observerRef = useRef<IntersectionObserver | null>(null);

  const fetchArticle = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getArticleDetail(slug);
      setArticle(data);
    } catch {
      setError("Article not found.");
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    fetchArticle();
  }, [fetchArticle]);

  // IntersectionObserver on h2 heading elements for active ToC highlight
  useEffect(() => {
    if (!article) return;
    observerRef.current?.disconnect();

    observerRef.current = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible.length > 0) {
          setActiveHeadingId(visible[0].target.id);
        }
      },
      { threshold: 0.3, rootMargin: "-80px 0px -60% 0px" },
    );

    const headingEls = document.querySelectorAll("h2[id]");
    headingEls.forEach((el) => observerRef.current?.observe(el));

    return () => observerRef.current?.disconnect();
  }, [article]);

  const handleHeadingClick = (id: string) => {
    setActiveHeadingId(id);
    document
      .getElementById(id)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard not available
    }
  };

  // ── Loading ──────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-[1400px] mx-auto px-4 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] xl:grid-cols-[240px_1fr_300px] gap-6">
            <div className="hidden lg:block space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className="h-8 bg-gray-200 rounded-lg animate-pulse"
                />
              ))}
            </div>
            <div className="bg-white rounded-2xl border border-gray-200 p-8 space-y-4">
              <div className="h-4 bg-gray-200 rounded animate-pulse w-1/3" />
              <div className="h-7 bg-gray-200 rounded animate-pulse" />
              <div className="h-4 bg-gray-100 rounded animate-pulse w-3/4" />
              {[1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className="h-4 bg-gray-100 rounded animate-pulse"
                />
              ))}
            </div>
            <div className="hidden xl:block space-y-3">
              <div className="h-48 bg-gray-200 rounded-xl animate-pulse" />
              <div className="h-32 bg-gray-200 rounded-xl animate-pulse" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !article) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-4xl mb-4">📭</p>
          <p className="text-gray-700 font-semibold mb-2">
            {error ?? "Article not found"}
          </p>
          <button
            onClick={() => router.push("/daily-ca")}
            className="text-sm text-blue-600 hover:underline"
          >
            ← Back to Daily CA
          </button>
        </div>
      </div>
    );
  }

  const headings = extractHeadings(article.body_md_processed ?? "");
  const parts = splitCallouts(article.body_md_processed ?? "");
  const gsColor = GS_COLORS[article.gs_paper] ?? GS_COLORS["CSAT"];
  const readMin = estimateReadTime(article.body_md_processed ?? "");
  const mdComponents = makeMarkdownComponents(activeHeadingId);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
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
              {article.title}
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

      {/* Layout */}
      <div className="max-w-[1400px] mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] xl:grid-cols-[240px_1fr_300px] gap-6">
          {/* Left — Section ToC */}
          <div className="hidden lg:block">
            <div className="sticky top-[60px]">
              <SectionToC
                headings={headings}
                activeId={activeHeadingId}
                onHeadingClick={handleHeadingClick}
              />
            </div>
          </div>

          {/* Main — Article */}
          <article className="rounded-2xl border border-gray-200 bg-white shadow-sm">
            {/* Header */}
            <div className="px-6 pt-6 pb-4">
              {/* Meta */}
              <div className="flex flex-wrap items-center gap-2 mb-3">
                {article.gs_paper && (
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-xs font-bold ${gsColor}`}
                  >
                    {article.gs_paper}
                  </span>
                )}
                <span className="text-xs text-gray-500">
                  {article.subject_name}
                </span>
                <span className="text-xs text-gray-300">·</span>
                <span className="text-xs text-gray-400">
                  {formatDate(article.published_date)}
                </span>
                <span className="text-xs text-gray-300">·</span>
                <span className="text-xs text-gray-400">
                  {readMin} min read
                </span>
              </div>

              {/* Title */}
              <h1 className="text-xl font-bold text-blue-900 leading-snug mb-3">
                {article.title}
              </h1>

              {/* News context */}
              {article.news_context && (
                <p className="text-sm text-gray-500 italic leading-relaxed border-l-2 border-gray-200 pl-3 mb-4">
                  {article.news_context}
                </p>
              )}

              {/* In Summary */}
              {article.body_md_processed && (
                <InSummaryBox bodyMd={article.body_md_processed} />
              )}
            </div>

            {/* Body */}
            <div className="px-6 pb-6">
              {parts.map((part, i) =>
                part.type === "callout" ? (
                  <CalloutBlock key={i} content={part.content} />
                ) : (
                  <ReactMarkdown
                    key={i}
                    remarkPlugins={[remarkGfm]}
                    components={mdComponents}
                  >
                    {part.content}
                  </ReactMarkdown>
                ),
              )}

              {/* Tags */}
              {article.tags.length > 0 && (
                <div className="mt-5 pt-4 border-t border-gray-100">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                    Tags
                  </p>
                  <TagChips tags={article.tags} />
                </div>
              )}

              {/* Concepts — mobile only (right panel hidden on small screens) */}
              {article.concept_links.length > 0 && (
                <div className="mt-4 xl:hidden">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                    Concepts Mentioned
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {article.concept_links.map((c) => (
                      <ConceptCard key={c.id} concept={c} />
                    ))}
                  </div>
                </div>
              )}

              {/* Sources */}
              <SourceAccordion sources={article.sources_used ?? []} />
            </div>
          </article>

          {/* Right — always visible on xl */}
          <div className="hidden xl:block">
            <div className="sticky top-[60px]">
              <RightPanel article={article} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
