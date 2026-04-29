"use client";

/**
 * engines/social/comments-section.tsx — Threaded comment section (Phase I).
 *
 * Behaviour:
 *   - Lazy fetch: first load fires only when isOpen becomes true.
 *   - Top-level comments paginated (20 per page) with "Load more" button.
 *   - Each comment: avatar initials, display name, relative time, body.
 *   - Inline reply input (1 level deep — matches backend constraint).
 *   - Edit / Delete visible only to comment owner.
 *   - Soft-deleted comments rendered as "[deleted]" in italic grey.
 *   - Optimistic append on post; reverts on API error.
 *   - Auth-guarded write actions — guests see "Login to comment" prompt.
 *
 * Note: Flag endpoint is not yet in the backend (Phase E admin only).
 *       Flag button is omitted until a dedicated POST /social/comments/<id>/flag/
 *       endpoint is added.
 */

import {
  Check,
  ChevronDown,
  ChevronUp,
  CornerDownRight,
  Pencil,
  Send,
  Trash2,
  X,
} from "lucide-react";
import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";

import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/lib/auth/useAuth";
import { getProfile } from "@/lib/api/userstate";
import {
  type Comment,
  type ContentType,
  deleteComment,
  editComment,
  getComments,
  postComment,
} from "@/lib/api/social";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────

interface CommentsSectionProps {
  contentType: ContentType;
  contentId: string;
  isOpen: boolean;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function initials(name: string): string {
  if (!name || name === "[deleted]") return "?";
  return name
    .trim()
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

const MAX_BODY = 1000;

// ── CommentInput ──────────────────────────────────────────────────────────────

interface CommentInputProps {
  placeholder?: string;
  onSubmit: (body: string) => Promise<void>;
  onCancel?: () => void;
  autoFocus?: boolean;
}

function CommentInput({
  placeholder = "Write a comment…",
  onSubmit,
  onCancel,
  autoFocus = false,
}: CommentInputProps) {
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (autoFocus) textareaRef.current?.focus();
  }, [autoFocus]);

  const handleSubmit = async () => {
    const trimmed = body.trim();
    if (!trimmed || submitting) return;
    setSubmitting(true);
    try {
      await onSubmit(trimmed);
      setBody("");
    } finally {
      setSubmitting(false);
    }
  };

  const remaining = MAX_BODY - body.length;

  return (
    <div className="flex flex-col gap-1.5">
      <textarea
        ref={textareaRef}
        value={body}
        onChange={(e) => setBody(e.target.value.slice(0, MAX_BODY))}
        placeholder={placeholder}
        rows={3}
        className="w-full resize-none rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSubmit();
        }}
      />
      <div className="flex items-center justify-between">
        <span
          className={cn(
            "text-xs",
            remaining < 50 ? "text-rose-500 font-medium" : "text-gray-400",
          )}
        >
          {remaining} / {MAX_BODY}
        </span>
        <div className="flex items-center gap-2">
          {onCancel && (
            <button
              onClick={onCancel}
              className="rounded px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
          )}
          <button
            onClick={handleSubmit}
            disabled={!body.trim() || submitting}
            className={cn(
              "flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors",
              body.trim() && !submitting
                ? "bg-blue-600 text-white hover:bg-blue-700"
                : "bg-gray-100 text-gray-400 cursor-not-allowed",
            )}
          >
            <Send className="h-3 w-3" />
            {submitting ? "Posting…" : "Post"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── EditInput ─────────────────────────────────────────────────────────────────

interface EditInputProps {
  initialBody: string;
  onSave: (body: string) => Promise<void>;
  onCancel: () => void;
}

function EditInput({ initialBody, onSave, onCancel }: EditInputProps) {
  const [body, setBody] = useState(initialBody);
  const [saving, setSaving] = useState(false);
  const remaining = MAX_BODY - body.length;

  const handleSave = async () => {
    const trimmed = body.trim();
    if (!trimmed || saving) return;
    setSaving(true);
    try {
      await onSave(trimmed);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-1.5 mt-1">
      <textarea
        autoFocus
        value={body}
        onChange={(e) => setBody(e.target.value.slice(0, MAX_BODY))}
        rows={3}
        className="w-full resize-none rounded-lg border border-blue-300 bg-white px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-1 focus:ring-blue-400"
      />
      <div className="flex items-center justify-between">
        <span
          className={cn(
            "text-xs",
            remaining < 50 ? "text-rose-500 font-medium" : "text-gray-400",
          )}
        >
          {remaining} / {MAX_BODY}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={onCancel}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
          >
            <X className="h-3 w-3" /> Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!body.trim() || saving}
            className={cn(
              "flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors",
              body.trim() && !saving
                ? "bg-blue-600 text-white hover:bg-blue-700"
                : "bg-gray-100 text-gray-400 cursor-not-allowed",
            )}
          >
            <Check className="h-3 w-3" />
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── CommentItem ───────────────────────────────────────────────────────────────

interface CommentItemProps {
  comment: Comment;
  currentUserId: string | null;
  currentUserAvatarUrl?: string;
  contentType: ContentType;
  contentId: string;
  isReply?: boolean;
  onReplyPosted?: (reply: Comment) => void;
  onUpdated: (updated: Comment) => void;
  onDeleted: (id: string) => void;
}

function CommentItem({
  comment,
  currentUserId,
  currentUserAvatarUrl,
  contentType,
  contentId,
  isReply = false,
  onReplyPosted,
  onUpdated,
  onDeleted,
}: CommentItemProps) {
  const { toast } = useToast();
  const isOwner = currentUserId === comment.user_id;
  const isDeleted = comment.is_deleted;

  const [repliesOpen, setRepliesOpen] = useState(false);
  const [replyInputOpen, setReplyInputOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // ── Reply post ─────────────────────────────────────────────────────────

  const handleReply = async (body: string) => {
    try {
      const newReply = await postComment({
        content_type: contentType,
        content_id: contentId,
        body,
        parent_id: comment.id,
      });
      onReplyPosted?.(newReply);
      setReplyInputOpen(false);
      setRepliesOpen(true);
    } catch {
      toast({
        title: "Could not post reply",
        description: "Please try again.",
        variant: "destructive",
      });
      throw new Error("reply failed"); // keeps CommentInput in submitting=false
    }
  };

  // ── Edit save ──────────────────────────────────────────────────────────

  const handleEditSave = async (body: string) => {
    try {
      const updated = await editComment(comment.id, body);
      onUpdated(updated);
      setEditing(false);
    } catch {
      toast({
        title: "Could not save edit",
        description: "Please try again.",
        variant: "destructive",
      });
      throw new Error("edit failed");
    }
  };

  // ── Delete ─────────────────────────────────────────────────────────────

  const handleDelete = async () => {
    if (!window.confirm("Delete this comment? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await deleteComment(comment.id);
      onDeleted(comment.id);
    } catch {
      toast({
        title: "Could not delete comment",
        description: "Please try again.",
        variant: "destructive",
      });
    } finally {
      setDeleting(false);
    }
  };

  const replyCount = comment.replies?.length ?? 0;

  return (
    <div className={cn("flex gap-2.5", isReply && "ml-8 mt-2")}>
      {/* Avatar */}
      <div className="flex-shrink-0 mt-0.5">
        {isOwner && currentUserAvatarUrl ? (
          <div
            className={cn(
              "relative rounded-full overflow-hidden",
              isReply ? "h-7 w-7" : "h-8 w-8",
            )}
          >
            <Image
              src={currentUserAvatarUrl}
              alt="You"
              fill
              className="object-cover"
              sizes={isReply ? "28px" : "32px"}
            />
          </div>
        ) : (
          <div
            className={cn(
              "flex items-center justify-center rounded-full bg-gradient-to-br font-semibold text-white select-none",
              isReply ? "h-7 w-7 text-xs" : "h-8 w-8 text-sm",
              isDeleted
                ? "from-gray-300 to-gray-400"
                : "from-blue-400 to-indigo-500",
            )}
          >
            {initials(comment.user_display_name)}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex flex-wrap items-baseline gap-1.5 mb-0.5">
          <span
            className={cn(
              "text-sm font-semibold",
              isDeleted ? "text-gray-400" : "text-gray-800",
            )}
          >
            {comment.user_display_name}
          </span>
          <span className="text-xs text-gray-400">
            {timeAgo(comment.created_at)}
          </span>
          {comment.edited_at && !isDeleted && (
            <span className="text-xs text-gray-400 italic">(edited)</span>
          )}
        </div>

        {/* Comment body or inline edit */}
        {editing ? (
          <EditInput
            initialBody={comment.body}
            onSave={handleEditSave}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <p
            className={cn(
              "text-sm leading-relaxed whitespace-pre-wrap break-words",
              isDeleted ? "text-gray-400 italic" : "text-gray-700",
            )}
          >
            {isDeleted ? "[deleted]" : comment.body}
          </p>
        )}

        {/* Action row */}
        {!isDeleted && !editing && (
          <div className="mt-1.5 flex items-center gap-3">
            {/* Reply — only on top-level comments */}
            {!isReply && (
              <button
                onClick={() => setReplyInputOpen((v) => !v)}
                className="flex items-center gap-1 text-xs text-gray-400 hover:text-blue-600 transition-colors"
              >
                <CornerDownRight className="h-3 w-3" />
                Reply
              </button>
            )}

            {/* Edit (owner only) */}
            {isOwner && (
              <button
                onClick={() => setEditing(true)}
                className="flex items-center gap-1 text-xs text-gray-400 hover:text-amber-600 transition-colors"
              >
                <Pencil className="h-3 w-3" />
                Edit
              </button>
            )}

            {/* Delete (owner only) */}
            {isOwner && (
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-1 text-xs text-gray-400 hover:text-rose-600 transition-colors disabled:opacity-50"
              >
                <Trash2 className="h-3 w-3" />
                {deleting ? "Deleting…" : "Delete"}
              </button>
            )}
          </div>
        )}

        {/* Reply input */}
        {replyInputOpen && (
          <div className="mt-2">
            <CommentInput
              placeholder="Write a reply…"
              onSubmit={handleReply}
              onCancel={() => setReplyInputOpen(false)}
              autoFocus
            />
          </div>
        )}

        {/* Replies toggle */}
        {!isReply && replyCount > 0 && (
          <button
            onClick={() => setRepliesOpen((v) => !v)}
            className="mt-2 flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700"
          >
            {repliesOpen ? (
              <>
                <ChevronUp className="h-3 w-3" />
                Hide {replyCount} {replyCount === 1 ? "reply" : "replies"}
              </>
            ) : (
              <>
                <ChevronDown className="h-3 w-3" />
                {replyCount} {replyCount === 1 ? "reply" : "replies"}
              </>
            )}
          </button>
        )}

        {/* Replies list */}
        {!isReply && repliesOpen && comment.replies?.length > 0 && (
          <div className="mt-1 border-l-2 border-gray-100 pl-1">
            {comment.replies.map((reply) => (
              <CommentItem
                key={reply.id}
                comment={reply}
                currentUserId={currentUserId}
                currentUserAvatarUrl={currentUserAvatarUrl}
                contentType={contentType}
                contentId={contentId}
                isReply
                onUpdated={(updated) => {
                  // bubble updated reply into parent comment's replies array
                  // handled by parent via onUpdated with synthetic merged comment
                  const merged: Comment = {
                    ...comment,
                    replies: comment.replies.map((r) =>
                      r.id === updated.id ? updated : r,
                    ),
                  };
                  onUpdated(merged);
                }}
                onDeleted={(deletedId) => {
                  const merged: Comment = {
                    ...comment,
                    replies: comment.replies.filter((r) => r.id !== deletedId),
                  };
                  onUpdated(merged);
                }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── CommentsSection ───────────────────────────────────────────────────────────

export function CommentsSection({
  contentType,
  contentId,
  isOpen,
}: CommentsSectionProps) {
  const { user, isAuthenticated } = useAuth();
  const { toast } = useToast();
  const [currentUserAvatarUrl, setCurrentUserAvatarUrl] = useState<string>("");

  useEffect(() => {
    if (!isAuthenticated) return;
    getProfile()
      .then((p) => setCurrentUserAvatarUrl(p.avatar_url || ""))
      .catch(() => {});
  }, [isAuthenticated]);

  const [comments, setComments] = useState<Comment[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [fetchedOnce, setFetchedOnce] = useState(false);
  const [error, setError] = useState(false);

  const hasMore = comments.length < totalCount;

  // ── Lazy initial fetch ──────────────────────────────────────────────────

  useEffect(() => {
    if (!isOpen || fetchedOnce) return;

    let cancelled = false;
    setLoading(true);
    setError(false);

    getComments(contentType, contentId, 1, 20)
      .then((data) => {
        if (!cancelled) {
          setComments(data.results);
          setTotalCount(data.count);
          setPage(1);
          setFetchedOnce(true);
        }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, fetchedOnce, contentType, contentId]);

  // ── Load more ───────────────────────────────────────────────────────────

  const handleLoadMore = async () => {
    if (loadingMore || !hasMore) return;
    const nextPage = page + 1;
    setLoadingMore(true);
    try {
      const data = await getComments(contentType, contentId, nextPage, 20);
      setComments((prev) => [...prev, ...data.results]);
      setTotalCount(data.count);
      setPage(nextPage);
    } catch {
      toast({
        title: "Could not load more comments",
        variant: "destructive",
      });
    } finally {
      setLoadingMore(false);
    }
  };

  // ── Post top-level comment ──────────────────────────────────────────────

  const handlePost = async (body: string) => {
    // Optimistic: build a local placeholder comment
    const optimistic: Comment = {
      id: `optimistic-${Date.now()}`,
      user_id: user?.id ?? "",
      user_display_name: user?.full_name || user?.email || "You",
      body,
      parent_id: null,
      replies: [],
      created_at: new Date().toISOString(),
      edited_at: null,
      is_deleted: false,
    };

    setComments((prev) => [optimistic, ...prev]);
    setTotalCount((c) => c + 1);

    try {
      const real = await postComment({
        content_type: contentType,
        content_id: contentId,
        body,
      });
      // Replace optimistic with real
      setComments((prev) =>
        prev.map((c) => (c.id === optimistic.id ? real : c)),
      );
    } catch {
      // Revert optimistic
      setComments((prev) => prev.filter((c) => c.id !== optimistic.id));
      setTotalCount((c) => Math.max(0, c - 1));
      toast({
        title: "Could not post comment",
        description: "Please try again.",
        variant: "destructive",
      });
      throw new Error("post failed"); // keeps CommentInput button enabled
    }
  };

  // ── Reply posted callback ───────────────────────────────────────────────

  const handleReplyPosted = useCallback((parentId: string, reply: Comment) => {
    setComments((prev) =>
      prev.map((c) =>
        c.id === parentId
          ? { ...c, replies: [...(c.replies ?? []), reply] }
          : c,
      ),
    );
  }, []);

  // ── Update / delete callbacks ───────────────────────────────────────────

  const handleUpdated = useCallback((updated: Comment) => {
    setComments((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  }, []);

  const handleDeleted = useCallback((id: string) => {
    // Mark as deleted in-place (soft delete — thread stays)
    setComments((prev) =>
      prev.map((c) =>
        c.id === id
          ? {
              ...c,
              is_deleted: true,
              body: "[deleted]",
              user_display_name: "[deleted]",
            }
          : c,
      ),
    );
    setTotalCount((c) => Math.max(0, c - 1));
  }, []);

  // ── Render ──────────────────────────────────────────────────────────────

  if (!isOpen) return null;

  return (
    <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50 px-4 py-4 shadow-sm">
      {/* Header */}
      <p className="mb-3 text-sm font-semibold text-gray-700">
        {totalCount > 0
          ? `${totalCount} Comment${totalCount !== 1 ? "s" : ""}`
          : "Comments"}
      </p>

      {/* Comment input — guests see the nudge in SocialBar; only show input when authenticated */}
      {isAuthenticated && (
        <div className="mb-4">
          <CommentInput onSubmit={handlePost} />
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex gap-2.5 animate-pulse">
              <div className="h-8 w-8 flex-shrink-0 rounded-full bg-gray-200" />
              <div className="flex-1 space-y-2 py-1">
                <div className="h-3 w-1/4 rounded bg-gray-200" />
                <div className="h-3 w-3/4 rounded bg-gray-200" />
                <div className="h-3 w-1/2 rounded bg-gray-200" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <p className="text-sm text-gray-400 text-center py-4">
          Could not load comments.{" "}
          <button
            onClick={() => setFetchedOnce(false)}
            className="text-blue-600 hover:underline"
          >
            Retry
          </button>
        </p>
      )}

      {/* Empty state */}
      {!loading && !error && fetchedOnce && comments.length === 0 && (
        <p className="text-sm text-gray-400 text-center py-4 italic">
          No comments yet. Be the first!
        </p>
      )}

      {/* Comment list */}
      {!loading && !error && comments.length > 0 && (
        <div className="space-y-4">
          {comments.map((comment) => (
            <CommentItem
              key={comment.id}
              comment={comment}
              currentUserId={user?.id ?? null}
              currentUserAvatarUrl={currentUserAvatarUrl}
              contentType={contentType}
              contentId={contentId}
              onReplyPosted={(reply) => handleReplyPosted(comment.id, reply)}
              onUpdated={handleUpdated}
              onDeleted={handleDeleted}
            />
          ))}
        </div>
      )}

      {/* Load more */}
      {!loading && hasMore && (
        <button
          onClick={handleLoadMore}
          disabled={loadingMore}
          className="mt-4 w-full rounded-lg border border-gray-200 py-2 text-sm text-gray-500 hover:bg-gray-50 transition-colors disabled:opacity-50"
        >
          {loadingMore
            ? "Loading…"
            : `Load more (${totalCount - comments.length} remaining)`}
        </button>
      )}
    </div>
  );
}
