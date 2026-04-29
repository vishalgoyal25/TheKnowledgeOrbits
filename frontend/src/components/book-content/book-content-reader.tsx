"use client";

/**
 * BookContentReader — Right-side article reader panel.
 *
 * Renders a full book-quality UPSC article when a graph/tree node is clicked.
 * Fetches from: GET /api/v1/book/content/{topic_id}/
 *
 * Features (FEATURES.md Task 6.3):
 *   - Renders `render_content` (formatted_content if available, else content_markdown)
 *   - Uses react-markdown + remark-gfm (existing project pattern)
 *   - Prose Tailwind table styling
 *   - Custom callout renderers:
 *       >[!infographic: "caption"]<  → dashed-border placeholder card + 🖼️ icon
 *       > **💡 UPSC High-Yield Focus:** ... → glassmorphism highlight callout
 *       Standard blockquote → left-border quote style
 *   - See Also section: CrossReference links call onSeeAlsoClick to navigate graph
 *   - Quality score badge: green >80 · yellow 65-80 · red <65
 *   - Word count + estimated read time
 */

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BookOpen, ExternalLink, AlertCircle, PenLine } from "lucide-react";

import { getBookContent } from "@/lib/api/book-content";
import { SocialBar } from "@/components/social/social-bar";
import { cn } from "@/lib/utils";
import type {
  BookContent,
  ContentMedia,
  CrossReference,
} from "@/types/book-content";

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────

/** Recursively extract plain text from an MDAST node (used to strip emoji prefix). */
function extractNodeText(node: unknown): string {
  if (!node || typeof node !== "object") return "";
  const n = node as Record<string, unknown>;
  if (n.type === "text") return String(n.value ?? "");
  if (Array.isArray(n.children)) {
    return (n.children as unknown[]).map(extractNodeText).join("");
  }
  return "";
}

/**
 * Detect if a blockquote node is one of our special callout types.
 * We inspect the raw text content of the children.
 */
function detectBlockquoteType(
  rawText: string,
): "infographic" | "upsc-focus" | "standard" {
  if (
    /^\s*>\s*\[!infographic:/i.test(rawText) ||
    rawText.includes("[!infographic:")
  ) {
    return "infographic";
  }
  if (
    rawText.includes("💡 UPSC High-Yield Focus") ||
    rawText.includes("UPSC High-Yield Focus")
  ) {
    return "upsc-focus";
  }
  return "standard";
}

// ─────────────────────────────────────────────────────────────────────────────
// SUB-COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────

/** Light-blue UPSC High-Yield Focus callout box */
function UpscFocusCallout({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-3 rounded-lg border border-blue-200 bg-blue-50/70 px-4 py-3">
      <div className="flex items-start gap-2">
        <PenLine className="h-3.5 w-3.5 flex-shrink-0 mt-0.5 text-blue-500" />
        <div className="text-sm leading-relaxed text-blue-900/90 font-medium">
          <span className="text-[11px] font-bold uppercase tracking-wider text-blue-600 mr-1">
            Important:
          </span>
          {children}
        </div>
      </div>
    </div>
  );
}

/** Standard blockquote */
function StandardBlockquote({ children }: { children: React.ReactNode }) {
  return (
    <blockquote className="my-4 border-l-4 border-primary/30 pl-4 py-1 bg-muted/30 rounded-r-lg italic text-muted-foreground text-sm leading-relaxed">
      {children}
    </blockquote>
  );
}

/** See Also link row */
function SeeAlsoLink({
  ref: xref,
  onClick,
}: {
  ref: CrossReference;
  onClick: (topicId: string, topicName: string) => void;
}) {
  const label = xref.display_label || xref.target_topic_name;
  const badgeColors: Record<string, string> = {
    see_also: "bg-blue-100   text-blue-700",
    prerequisite: "bg-purple-100 text-purple-700",
    continuation: "bg-green-100  text-green-700",
    contrast: "bg-orange-100 text-orange-700",
  };

  return (
    <button
      onClick={() => onClick(xref.target_topic_id, xref.target_topic_name)}
      className="flex items-center gap-2 w-full text-left px-3 py-2.5 rounded-lg hover:bg-muted/60 transition-colors group"
    >
      <ExternalLink className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary flex-shrink-0 transition-colors" />
      <span className="text-sm text-foreground group-hover:text-primary transition-colors flex-1">
        {label}
      </span>
      <span
        className={cn(
          "text-xs px-1.5 py-0.5 rounded font-medium flex-shrink-0",
          badgeColors[xref.ref_type] ?? "bg-muted text-muted-foreground",
        )}
      >
        {xref.ref_type.replace("_", " ")}
      </span>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MARKDOWN RENDERER
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Extract the infographic caption from raw blockquote text.
 * Matches patterns like `[!infographic: Map of British India 1773]`.
 * Returns null if no infographic marker is found.
 */
function extractInfographicCaption(rawText: string): string | null {
  const match = rawText.match(/\[!infographic:\s*([^\]]+)\]/i);
  return match ? match[1].trim() : null;
}

/**
 * Find a ContentMedia entry whose position_marker contains the given caption.
 * Returns the media object if found AND cloudinary_url is populated.
 */
function resolveInfographicMedia(
  caption: string,
  mediaAssets: ContentMedia[],
): ContentMedia | null {
  const found = mediaAssets.find(
    (m) =>
      m.cloudinary_url.length > 0 &&
      m.position_marker.toLowerCase().includes(caption.toLowerCase()),
  );
  return found ?? null;
}

function BookMarkdown({
  content,
  mediaAssets,
}: {
  content: string;
  mediaAssets: ContentMedia[];
}) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Headings
        h1: ({ ...props }) => (
          <h1
            className="text-xl sm:text-2xl font-bold mt-8 mb-4 text-foreground border-b border-border pb-2 break-words"
            {...props}
          />
        ),
        h2: ({ ...props }) => (
          <h2
            className="text-base sm:text-lg font-bold mt-6 mb-3 text-primary break-words"
            {...props}
          />
        ),
        h3: ({ ...props }) => (
          <h3
            className="text-sm font-bold mt-6 mb-2 text-indigo-700 uppercase tracking-wider border-b border-indigo-100 pb-1.5 break-words"
            {...props}
          />
        ),

        // Paragraph
        p: ({ ...props }) => (
          <p
            className="mb-3 leading-relaxed text-sm text-foreground/90 break-words overflow-wrap-anywhere"
            {...props}
          />
        ),

        // Lists
        ul: ({ ...props }) => (
          <ul
            className="list-disc pl-5 mb-3 space-y-1 text-sm text-foreground/90"
            {...props}
          />
        ),
        ol: ({ ...props }) => (
          <ol
            className="list-decimal pl-5 mb-3 space-y-1 text-sm text-foreground/90"
            {...props}
          />
        ),
        li: ({ ...props }) => (
          <li className="leading-relaxed marker:text-primary" {...props} />
        ),

        // Tables — light blue header + visible grid
        table: ({ ...props }) => (
          <div className="my-4 overflow-x-auto rounded-lg border border-blue-100">
            <table className="w-full text-sm border-collapse" {...props} />
          </div>
        ),
        thead: ({ ...props }) => <thead className="bg-blue-50" {...props} />,
        th: ({ ...props }) => (
          <th
            className="px-2 py-1.5 sm:px-3 sm:py-2 text-left text-xs font-semibold text-blue-700 uppercase tracking-wider border-b border-blue-200 bg-blue-50"
            {...props}
          />
        ),
        td: ({ ...props }) => (
          <td
            className="px-2 py-1.5 sm:px-3 sm:py-2 text-sm text-foreground/90 border-b border-blue-100 border-r border-r-blue-100/60 last:border-r-0 align-top break-words"
            {...props}
          />
        ),
        tr: ({ ...props }) => (
          <tr
            className="even:bg-blue-50/30 hover:bg-blue-50/60 transition-colors"
            {...props}
          />
        ),

        // Strong / em
        strong: ({ ...props }) => (
          <strong className="font-semibold text-foreground" {...props} />
        ),
        em: ({ ...props }) => (
          <em className="italic text-foreground/80" {...props} />
        ),

        // Blockquote — detect callout type from raw string children
        blockquote: ({ node, children, ...props }) => {
          // Extract raw text for type detection
          let rawText = "";
          try {
            rawText = node ? JSON.stringify(node) : String(children);
          } catch {
            rawText = String(children);
          }

          const type = detectBlockquoteType(rawText);

          if (type === "infographic") {
            const caption = extractInfographicCaption(rawText);
            if (caption) {
              const media = resolveInfographicMedia(caption, mediaAssets);
              if (media) {
                return (
                  <figure className="my-5">
                    <Image
                      src={media.cloudinary_url}
                      alt={media.alt_text || caption}
                      width={800}
                      height={450}
                      className="rounded-lg w-full h-auto"
                      sizes="(max-width: 768px) 100vw, (max-width: 1200px) 60vw, 800px"
                    />
                    {(media.caption || caption) && (
                      <figcaption className="mt-2 text-center text-xs text-muted-foreground italic">
                        {media.caption || caption}
                      </figcaption>
                    )}
                  </figure>
                );
              }
            }
            // No Cloudinary URL for this infographic → render nothing
            return null;
          }

          if (type === "upsc-focus") {
            // Strip the leading emoji + label from plain text so the component
            // renders only the actual insight text (no duplicate 💡 or label).
            const fullText = extractNodeText(node)
              .replace(/💡\s*UPSC High-Yield Focus:\s*/i, "")
              .trim();
            return <UpscFocusCallout>{fullText}</UpscFocusCallout>;
          }

          return <StandardBlockquote {...props}>{children}</StandardBlockquote>;
        },

        // Inline code
        code: ({ children, className, ...props }) => {
          // Block code is rendered by pre; inline code has no language className
          const isBlock = className?.startsWith("language-");
          if (isBlock) {
            return (
              <code
                className="block font-mono text-xs leading-relaxed"
                {...props}
              >
                {children}
              </code>
            );
          }
          return (
            <code
              className="font-mono text-xs bg-muted px-1 py-0.5 rounded text-foreground/90"
              {...props}
            >
              {children}
            </code>
          );
        },

        // Code block wrapper
        pre: ({ ...props }) => (
          <pre
            className="my-4 overflow-x-auto rounded-lg bg-muted/60 border border-border px-4 py-3 text-xs font-mono leading-relaxed text-foreground/90"
            {...props}
          />
        ),

        // Images — Cloudinary → Next.js <Image> (optimised CDN); everything else → lazy <img>
        img: ({ src, alt }) => {
          if (!src) return null;
          const imgSrc = typeof src === "string" ? src : "";
          if (imgSrc.includes("cloudinary.com")) {
            return (
              <Image
                src={imgSrc}
                alt={alt ?? ""}
                width={800}
                height={450}
                className="rounded-lg my-4 w-full h-auto"
                sizes="(max-width: 768px) 100vw, (max-width: 1200px) 60vw, 800px"
              />
            );
          }
          return (
            <img
              src={imgSrc}
              alt={alt ?? ""}
              loading="lazy"
              className="rounded-lg my-4 w-full h-auto"
            />
          );
        },

        // Horizontal rule as section divider
        hr: () => <hr className="my-6 border-border/50" />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// EMPTY STATE
// ─────────────────────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground px-8 text-center">
      <BookOpen className="h-12 w-12 opacity-20" />
      <div>
        <p className="font-medium text-foreground/60">No article selected</p>
        <p className="text-sm mt-1 leading-relaxed">
          Click any node in the graph or outline to load its AI-generated UPSC
          content here.
        </p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PROPS
// ─────────────────────────────────────────────────────────────────────────────

interface BookContentReaderProps {
  /** UUID of the topic whose article to display. Null = empty state. */
  topicId: string | null;
  /** Display name shown in the header while loading / for context. */
  topicName?: string;
  /**
   * Called when user clicks a See Also cross-reference link.
   * The parent page should navigate the graph/tree to this node.
   */
  onSeeAlsoClick: (topicId: string, topicName: string) => void;
  className?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN COMPONENT
// ─────────────────────────────────────────────────────────────────────────────

export default function BookContentReader({
  topicId,
  topicName,
  onSeeAlsoClick,
  className,
}: BookContentReaderProps) {
  const [content, setContent] = useState<BookContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Fetch article whenever topicId changes ────────────────────────────────
  useEffect(() => {
    if (!topicId) {
      setContent(null);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    setContent(null);

    getBookContent(topicId)
      .then((data) => {
        setContent(data);
        setLoading(false);
      })
      .catch(() => {
        setError(
          "Could not load article. The content may not be generated yet.",
        );
        setLoading(false);
      });
  }, [topicId]);

  const handleSeeAlso = useCallback(
    (id: string, name: string) => {
      onSeeAlsoClick(id, name);
    },
    [onSeeAlsoClick],
  );

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div
      className={cn(
        "flex flex-col h-full w-full overflow-hidden border border-border rounded-lg bg-background",
        className,
      )}
    >
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 px-3 sm:px-5 py-3 sm:py-4 border-b border-border bg-muted/20">
        {/* Empty state header */}
        {!topicId && (
          <p className="text-sm text-muted-foreground">
            Select a node to read its article
          </p>
        )}

        {/* Loading header */}
        {topicId && loading && (
          <div className="space-y-2">
            <div className="h-4 w-48 rounded bg-muted animate-pulse" />
            <div className="h-3 w-32 rounded bg-muted animate-pulse" />
          </div>
        )}

        {/* Loaded header */}
        {content && !loading && (
          <div className="space-y-2">
            {/* Node type badge */}
            <span className="inline-block text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border border-primary/30 bg-primary/10 text-primary">
              {content.topic_name
                ? content.topic_name.length > 0
                  ? "📄 Article"
                  : ""
                : "📄 Article"}
            </span>

            {/* Title */}
            <h2 className="text-lg font-bold leading-snug text-foreground">
              {content.topic_name}
            </h2>
          </div>
        )}

        {/* Error header */}
        {error && !loading && topicName && (
          <div>
            <p className="text-sm font-semibold text-foreground">{topicName}</p>
          </div>
        )}
      </div>

      {/* ── Scrollable body ─────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto scroll-smooth px-3 sm:px-5 py-4 sm:py-5 space-y-4 [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-thumb]:rounded [&::-webkit-scrollbar-thumb]:bg-border">
        {/* Empty state */}
        {!topicId && <EmptyState />}

        {/* Loading skeleton */}
        {loading && (
          <div className="space-y-3 animate-pulse">
            <div className="h-3 w-full rounded bg-muted" />
            <div className="h-3 w-5/6 rounded bg-muted" />
            <div className="h-3 w-4/6 rounded bg-muted" />
            <div className="h-5 w-1/3 rounded bg-muted mt-6" />
            <div className="h-3 w-full rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
            <div className="h-3 w-3/4 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted mt-4" />
            <div className="h-3 w-5/6 rounded bg-muted" />
          </div>
        )}

        {/* Error state */}
        {!loading && error && (
          <div className="flex flex-col items-center gap-3 py-12 text-center text-muted-foreground">
            <AlertCircle className="h-10 w-10 text-destructive/50" />
            <p className="text-sm text-destructive/80">{error}</p>
            <p className="text-xs text-muted-foreground/70">
              Content for this topic may not be generated yet. Run the
              generation pipeline to create it.
            </p>
          </div>
        )}

        {/* Article content */}
        {!loading && !error && content && (
          <div className="max-w-3xl mx-auto w-full">
            {/* Main markdown article */}
            <BookMarkdown
              content={content.render_content}
              mediaAssets={content.media_assets ?? []}
            />

            {/* ── See Also section ─────────────────────────────────────────── */}
            {content.cross_references.length > 0 && (
              <div className="mt-8 pt-6 border-t border-border">
                <h3 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-3 flex items-center gap-2">
                  <ExternalLink className="h-3.5 w-3.5" />
                  See Also
                </h3>
                <div className="space-y-1">
                  {content.cross_references.map((xref: CrossReference) => (
                    <SeeAlsoLink
                      key={xref.id}
                      ref={xref}
                      onClick={handleSeeAlso}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* ── Footer metadata ──────────────────────────────────────────── */}
            <div className="mt-8 pt-4 border-t border-border/50 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground/60">
              <span>Subject: {content.subject_name}</span>
              <span>
                {content.generation_pass > 1
                  ? `Refined (${content.generation_pass} passes)`
                  : "First-pass quality"}
              </span>
            </div>

            {/* ── Social bar ───────────────────────────────────────────────── */}
            <div className="mt-4 pt-4 border-t border-border/50">
              <SocialBar
                key={content.id}
                contentType="book_article"
                contentId={content.id}
                shareUrl={`https://www.theknowledgeorbits.com/knowledge?topic=${content.topic_id}`}
                shareTitle={content.topic_name}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
