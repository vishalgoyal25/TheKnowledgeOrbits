/**
 * P3.1 — Article Detail Page (Server Component + ISR)
 *
 * Converted from "use client" + useEffect (CSR) to a Next.js async server
 * component with ISR (revalidate: 3600).
 *
 * Before: Browser downloads empty HTML → JS boots (~500ms) → useEffect fires
 *         → fetch /api/…/article/{slug}/ (~200ms) → React renders content
 *         Total TTFB to content: 700ms+ before user sees any article text
 *
 * After:  Vercel CDN serves pre-rendered HTML in <50ms. Cached for 1 hour.
 *         Only 2 tiny client components: ArticleTopBar (back+share) and
 *         ScrollSpyToC (IntersectionObserver). Everything else is static HTML.
 *
 * SEO:    generateMetadata provides <title> and <meta description> for Google.
 */

import { notFound } from "next/navigation";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Metadata } from "next";

import { DailyCaArticleDetail } from "@/lib/api/daily-ca";
import { InSummaryBox } from "@/components/daily-ca/in-summary-box";
import { CalloutBlock } from "@/components/daily-ca/callout-block";
import { TagChips } from "@/components/daily-ca/tag-chips";
import { SourceAccordion } from "@/components/daily-ca/source-accordion";
import { RightPanel } from "@/components/daily-ca/right-panel";
import { ConceptCard } from "@/components/daily-ca/concept-card";
import { ScrollSpyToC, Heading } from "./_components/scroll-spy-toc";
import { ArticleTopBar } from "./_components/article-top-bar";

// ── ISR — rebuild CDN cache every hour; articles are immutable after publish ──
export const revalidate = 3600;

// ── Server-side fetch (uses native fetch, not axios) ─────────────────────────

async function fetchArticle(
  slug: string,
): Promise<DailyCaArticleDetail | null> {
  const apiBase = (
    process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1"
  ).replace(/\/$/, "");

  try {
    const res = await fetch(`${apiBase}/daily-ca/article/${slug}/`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return res.json() as Promise<DailyCaArticleDetail>;
  } catch {
    return null;
  }
}

// ── SEO metadata (generated server-side per article) ─────────────────────────

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const article = await fetchArticle(params.slug);
  if (!article) return { title: "Article not found | TheKnowledgeOrbits" };
  return {
    title: `${article.title} | TheKnowledgeOrbits`,
    description: article.news_context || article.title,
    openGraph: {
      title: article.title,
      description: article.news_context || article.title,
      images: article.hero_image_url ? [article.hero_image_url] : [],
    },
  };
}

// ── Pure helpers (run server-side, no state needed) ──────────────────────────

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

// ── Static markdown components (no active-heading state — ToC handles it) ────

const markdownComponents = {
  h2: ({ children }: { children?: React.ReactNode }) => {
    const text =
      typeof children === "string" ? children : String(children ?? "");
    const id = slugToId(text);
    return (
      <h2
        id={id}
        className="text-base font-bold mt-6 mb-2 pb-1.5 border-b scroll-mt-20 text-gray-900 border-gray-100"
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
    <ul className="my-3 space-y-2 pl-1 border-l-2 border-blue-100 ml-1">
      {children}
    </ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="my-3 space-y-2 pl-5 list-decimal [&>li]:pl-1 [&>li]:text-sm [&>li]:text-gray-700 [&>li]:leading-relaxed marker:text-blue-500 marker:font-semibold">
      {children}
    </ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="text-sm text-gray-700 leading-relaxed flex gap-2 pl-3">
      <span className="flex-shrink-0 text-blue-500 font-bold mt-0.5 text-xs">
        ▸
      </span>
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

// ── GS badge colours ──────────────────────────────────────────────────────────

const GS_COLORS: Record<string, string> = {
  GS1: "bg-purple-100 text-purple-700 border-purple-200",
  GS2: "bg-blue-100 text-blue-700 border-blue-200",
  GS3: "bg-green-100 text-green-700 border-green-200",
  GS4: "bg-orange-100 text-orange-700 border-orange-200",
  CSAT: "bg-gray-100 text-gray-600 border-gray-200",
};

// ── Page (Server Component) ───────────────────────────────────────────────────

export default async function ArticleDetailPage({
  params,
}: {
  params: { slug: string };
}) {
  const article = await fetchArticle(params.slug);

  if (!article) notFound();

  const headings = extractHeadings(article.body_md_processed ?? "");
  const parts = splitCallouts(article.body_md_processed ?? "");
  const gsColor = GS_COLORS[article.gs_paper] ?? GS_COLORS["CSAT"];
  const readMin = estimateReadTime(article.body_md_processed ?? "");

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar — client component (back button + share) */}
      <ArticleTopBar title={article.title} />

      {/* Layout */}
      <div className="max-w-[1400px] mx-auto px-2 sm:px-4 py-4 sm:py-6">
        <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] xl:grid-cols-[240px_1fr_300px] gap-6">
          {/* Left — Scroll-spy ToC — client component */}
          <div className="hidden lg:block">
            <div className="sticky top-[60px]">
              <ScrollSpyToC headings={headings} />
            </div>
          </div>

          {/* Main — Article body (fully server-rendered) */}
          <article className="rounded-2xl border border-gray-200 bg-white shadow-sm">
            {/* Header */}
            <div className="px-4 sm:px-6 pt-5 sm:pt-6 pb-4">
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

              <h1 className="text-xl font-bold text-blue-900 leading-snug mb-3">
                {article.title}
              </h1>

              {article.news_context && (
                <p className="text-sm text-gray-500 italic leading-relaxed border-l-2 border-gray-200 pl-3 mb-4">
                  {article.news_context}
                </p>
              )}
            </div>

            {/* Hero Image */}
            {article.hero_image_url && (
              <div className="relative w-full h-56 sm:h-72 overflow-hidden">
                <Image
                  src={article.hero_image_url}
                  alt={article.title}
                  fill
                  className="object-cover"
                  sizes="(max-width: 768px) 100vw, 860px"
                  priority
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/20 via-transparent to-transparent" />
              </div>
            )}

            {/* In Summary */}
            {article.body_md_processed && (
              <div className="px-4 sm:px-6 pt-4">
                <InSummaryBox
                  bodyMd={article.body_md_processed}
                  newsContext={article.news_context}
                />
              </div>
            )}

            {/* Body */}
            <div className="px-4 sm:px-6 pb-6">
              {parts.map((part, i) =>
                part.type === "callout" ? (
                  <CalloutBlock key={i} content={part.content} />
                ) : (
                  <ReactMarkdown
                    key={i}
                    remarkPlugins={[remarkGfm]}
                    components={markdownComponents}
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

              {/* Concepts — mobile only */}
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

          {/* Right panel */}
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
