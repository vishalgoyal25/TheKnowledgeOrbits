"use client";

/**
 * engines/social/social-bar.tsx — Social interaction bar (Phase G, UI v2).
 *
 * Wrapped in an attractive card. Larger icons. Permanent "Log in" nudge
 * for guests. Works for all three content types.
 */

import { Heart, LogIn, MessageCircle } from "lucide-react";
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
  shareUrl: string;
  shareTitle: string;
  className?: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

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

    const prevLiked = liked;
    const prevCount = counts.like_count;
    setLiked(!prevLiked);
    setCounts((c) => ({
      ...c,
      like_count: prevLiked ? Math.max(0, c.like_count - 1) : c.like_count + 1,
    }));
    setLikeLoading(true);

    try {
      const result = await toggleLike(contentType, contentId);
      setLiked(result.liked);
      setCounts((c) => ({ ...c, like_count: result.like_count }));
    } catch {
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
    <div className={cn("flex flex-col gap-3", className)}>
      {/* ── Card ────────────────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-blue-100 bg-gradient-to-r from-blue-50 to-indigo-50 px-5 py-4 shadow-sm">
        {/* ── Button row ─────────────────────────────────────────────────── */}
        <div className="flex items-center gap-2">
          {/* Like */}
          <button
            onClick={handleLike}
            disabled={likeLoading}
            aria-label={liked ? "Unlike" : "Like"}
            className={cn(
              "flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all duration-150 select-none shadow-sm",
              liked
                ? "bg-rose-500 text-white hover:bg-rose-600 shadow-rose-200"
                : "bg-white text-gray-600 border border-gray-200 hover:border-rose-300 hover:text-rose-600 hover:bg-rose-50",
              likeLoading && "opacity-60 cursor-not-allowed",
            )}
          >
            <Heart
              className={cn(
                "h-5 w-5 transition-all duration-150",
                liked && "fill-white scale-110",
              )}
            />
            <span>{countsLoaded ? compactCount(counts.like_count) : "–"}</span>
          </button>

          {/* Comment */}
          <button
            onClick={() => setCommentsOpen((o) => !o)}
            aria-label={commentsOpen ? "Hide comments" : "Show comments"}
            className={cn(
              "flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all duration-150 select-none shadow-sm",
              commentsOpen
                ? "bg-blue-500 text-white hover:bg-blue-600 shadow-blue-200"
                : "bg-white text-gray-600 border border-gray-200 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50",
            )}
          >
            <MessageCircle
              className={cn("h-5 w-5", commentsOpen && "fill-white")}
            />
            <span>
              {countsLoaded ? compactCount(counts.comment_count) : "–"}
            </span>
          </button>

          {/* Share */}
          <ShareButton
            contentType={contentType}
            contentId={contentId}
            shareUrl={shareUrl}
            shareTitle={shareTitle}
            shareCount={countsLoaded ? counts.share_count : undefined}
            className="rounded-xl px-4 py-2.5 text-sm font-semibold bg-white border border-gray-200 shadow-sm hover:border-indigo-300 hover:text-indigo-600 hover:bg-indigo-50"
          />
        </div>

        {/* ── Permanent login nudge (guests only) ──────────────────────── */}
        {!isAuthenticated && (
          <div className="mt-3 flex items-center gap-2.5 rounded-xl border border-blue-100 bg-blue-50 px-4 py-2.5">
            <LogIn className="h-4 w-4 flex-shrink-0 text-blue-500" />
            <p className="text-sm text-blue-700">
              <a
                href="/auth/login"
                className="font-semibold underline underline-offset-2 hover:text-blue-900"
              >
                Log in
              </a>{" "}
              to like, comment, and join the discussion.
            </p>
          </div>
        )}
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
