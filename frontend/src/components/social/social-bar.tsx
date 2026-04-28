"use client";

/**
 * engines/social/social-bar.tsx — Social interaction bar (Phase G).
 *
 * Renders a compact horizontal bar with:
 *   ❤️ Like button   — optimistic toggle, auth-guarded
 *   💬 Comment count — toggles CommentsSection below (Phase I)
 *   📤 Share button  — upgrades to <ShareButton> popover in Phase H
 *
 * Works for all three content types: daily_ca_article, book_article, quiz.
 */

import { Heart, MessageCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { CommentsSection } from "@/components/social/comments-section";
import { ShareButton } from "@/components/social/share-button";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/lib/auth/useAuth";
import {
  type ContentType,
  type SocialCount,
  getSocialCount,
  toggleLike,
} from "@/lib/api/social";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────

interface SocialBarProps {
  contentType: ContentType;
  contentId: string;
  /** Full canonical URL used by the Share button (Phase H). */
  shareUrl: string;
  /** Article / quiz title used in share text (Phase H). */
  shareTitle: string;
  className?: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** 1234 → "1.2k"   1_200_000 → "1.2m"   999 → "999" */
function compactCount(n: number): string {
  if (n >= 1_000_000)
    return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}m`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, "")}k`;
  return String(n);
}

// ── Component ─────────────────────────────────────────────────────────────────

export function SocialBar({
  contentType,
  contentId,
  shareUrl,
  shareTitle,
  className,
}: SocialBarProps) {
  const { isAuthenticated } = useAuth();
  const { toast } = useToast();

  // ── State ─────────────────────────────────────────────────────────────────

  type CountState = Pick<
    SocialCount,
    "like_count" | "comment_count" | "share_count"
  >;

  const [counts, setCounts] = useState<CountState>({
    like_count: 0,
    comment_count: 0,
    share_count: 0,
  });
  const [liked, setLiked] = useState(false);
  const [likeLoading, setLikeLoading] = useState(false);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [countsLoaded, setCountsLoaded] = useState(false);

  // ── Fetch counts on mount ─────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;

    async function fetchCounts() {
      try {
        const data = await getSocialCount(contentType, contentId);
        if (!cancelled) {
          setCounts({
            like_count: data.like_count,
            comment_count: data.comment_count,
            share_count: data.share_count,
          });
          setLiked(data.user_liked);
          setCountsLoaded(true);
        }
      } catch {
        // Non-critical — counts stay at 0, bar still renders
        if (!cancelled) setCountsLoaded(true);
      }
    }

    fetchCounts();
    return () => {
      cancelled = true;
    };
  }, [contentType, contentId]);

  // ── Like toggle ───────────────────────────────────────────────────────────

  const handleLike = useCallback(async () => {
    if (!isAuthenticated) {
      toast({
        title: "Login required",
        description: "Please log in to like this content.",
        variant: "destructive",
      });
      return;
    }

    if (likeLoading) return;

    // Snapshot for potential revert
    const prevLiked = liked;
    const prevCount = counts.like_count;

    // Optimistic update
    setLiked(!prevLiked);
    setCounts((c) => ({
      ...c,
      like_count: prevLiked ? Math.max(0, c.like_count - 1) : c.like_count + 1,
    }));
    setLikeLoading(true);

    try {
      const result = await toggleLike(contentType, contentId);
      // Sync with server truth
      setLiked(result.liked);
      setCounts((c) => ({ ...c, like_count: result.like_count }));
    } catch {
      // Revert optimistic update on error
      setLiked(prevLiked);
      setCounts((c) => ({ ...c, like_count: prevCount }));
      toast({
        title: "Something went wrong",
        description: "Could not update your like. Please try again.",
        variant: "destructive",
      });
    } finally {
      setLikeLoading(false);
    }
  }, [
    isAuthenticated,
    liked,
    likeLoading,
    counts.like_count,
    contentType,
    contentId,
    toast,
  ]);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className={cn("flex flex-col", className)}>
      {/* ── Interaction bar ─────────────────────────────────────────────── */}
      <div className="flex items-center gap-1">
        {/* Like */}
        <button
          onClick={handleLike}
          disabled={likeLoading}
          aria-label={liked ? "Unlike" : "Like"}
          className={cn(
            "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors select-none",
            liked
              ? "text-rose-600 bg-rose-50 hover:bg-rose-100"
              : "text-gray-500 hover:text-rose-600 hover:bg-rose-50",
            likeLoading && "opacity-60 cursor-not-allowed",
          )}
        >
          <Heart
            className={cn(
              "h-4 w-4 transition-all duration-150",
              liked && "fill-rose-600 scale-110",
            )}
          />
          <span>{countsLoaded ? compactCount(counts.like_count) : "–"}</span>
        </button>

        {/* Comment count — toggles CommentsSection */}
        <button
          onClick={() => setCommentsOpen((open) => !open)}
          aria-label={commentsOpen ? "Hide comments" : "Show comments"}
          className={cn(
            "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors select-none",
            commentsOpen
              ? "text-blue-600 bg-blue-50 hover:bg-blue-100"
              : "text-gray-500 hover:text-blue-600 hover:bg-blue-50",
          )}
        >
          <MessageCircle
            className={cn(
              "h-4 w-4",
              commentsOpen && "fill-blue-100 stroke-blue-600",
            )}
          />
          <span>{countsLoaded ? compactCount(counts.comment_count) : "–"}</span>
        </button>

        {/* Share — Phase H ShareButton */}
        <ShareButton
          contentType={contentType}
          contentId={contentId}
          shareUrl={shareUrl}
          shareTitle={shareTitle}
          shareCount={countsLoaded ? counts.share_count : undefined}
        />
      </div>

      {/* ── CommentsSection ──────────────────────────────────────────────── */}
      <CommentsSection
        contentType={contentType}
        contentId={contentId}
        isOpen={commentsOpen}
      />
    </div>
  );
}
