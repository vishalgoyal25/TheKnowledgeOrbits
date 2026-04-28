/**
 * engines/social — Frontend API layer (Phase F).
 *
 * All read endpoints (getSocialCount, getComments) are public — no auth needed.
 * All write endpoints (toggleLike, postComment, editComment, deleteComment, logShare)
 * require the user to be logged in. The apiClient interceptor attaches the JWT
 * automatically when a token is present in localStorage.
 *
 * Base URL: /api/v1/social/  (registered in backend core/urls.py)
 */

import apiClient from "./client";

// ── Types ─────────────────────────────────────────────────────────────────────

export type ContentType = "daily_ca_article" | "book_article" | "quiz";

export type Platform =
  | "copy_link"
  | "whatsapp"
  | "twitter"
  | "telegram"
  | "other";

export interface SocialCount {
  content_type: ContentType;
  content_id: string;
  like_count: number;
  comment_count: number;
  share_count: number;
  /** True when the authenticated user has liked this item. Always false for guests. */
  user_liked: boolean;
}

export interface Comment {
  id: string;
  user_id: string;
  user_display_name: string;
  body: string;
  parent_id: string | null;
  replies: Comment[];
  created_at: string;
  edited_at: string | null;
  is_deleted: boolean;
}

export interface PaginatedComments {
  count: number;
  next: string | null;
  previous: string | null;
  results: Comment[];
}

// ── SocialCount ───────────────────────────────────────────────────────────────

/**
 * GET /api/v1/social/counts/
 *
 * Returns like / comment / share counts for any content item.
 * Returns all-zero counts when no social activity exists yet (no DB row).
 * `user_liked` is true only when an authenticated user has liked the item.
 */
export async function getSocialCount(
  contentType: ContentType,
  contentId: string,
): Promise<SocialCount> {
  const response = await apiClient.get<SocialCount>("/social/counts/", {
    params: { content_type: contentType, content_id: contentId },
  });
  return response.data;
}

// ── Like ──────────────────────────────────────────────────────────────────────

export interface LikeToggleResult {
  /** True = just liked, False = just unliked */
  liked: boolean;
  /** Fresh like_count after the toggle */
  like_count: number;
}

/**
 * POST /api/v1/social/likes/toggle/
 *
 * Idempotent toggle — like if not liked, unlike if already liked.
 * Requires authentication (401 if unauthenticated).
 */
export async function toggleLike(
  contentType: ContentType,
  contentId: string,
): Promise<LikeToggleResult> {
  const response = await apiClient.post<LikeToggleResult>(
    "/social/likes/toggle/",
    { content_type: contentType, content_id: contentId },
  );
  return response.data;
}

// ── Comments ──────────────────────────────────────────────────────────────────

/**
 * GET /api/v1/social/comments/
 *
 * Returns paginated top-level comments for a content item (oldest first).
 * Each comment includes up to 10 direct replies nested inside.
 * Public — no auth required.
 */
export async function getComments(
  contentType: ContentType,
  contentId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedComments> {
  const response = await apiClient.get<PaginatedComments>("/social/comments/", {
    params: {
      content_type: contentType,
      content_id: contentId,
      page,
      page_size: pageSize,
    },
  });
  return response.data;
}

export interface PostCommentPayload {
  content_type: ContentType;
  content_id: string;
  body: string;
  /** Omit for top-level; supply to reply to an existing comment. */
  parent_id?: string | null;
}

/**
 * POST /api/v1/social/comments/create/
 *
 * Creates a top-level comment or a 1-level reply.
 * Requires authentication.
 */
export async function postComment(
  payload: PostCommentPayload,
): Promise<Comment> {
  const response = await apiClient.post<Comment>(
    "/social/comments/create/",
    payload,
  );
  return response.data;
}

/**
 * PATCH /api/v1/social/comments/<uuid>/
 *
 * Edit the body of an owned comment.
 * Requires authentication + ownership.
 */
export async function editComment(
  commentId: string,
  body: string,
): Promise<Comment> {
  const response = await apiClient.patch<Comment>(
    `/social/comments/${commentId}/`,
    { body },
  );
  return response.data;
}

/**
 * DELETE /api/v1/social/comments/<uuid>/
 *
 * Soft-deletes an owned comment (preserves thread structure).
 * Returns 204 No Content on success.
 * Requires authentication + ownership.
 */
export async function deleteComment(commentId: string): Promise<void> {
  await apiClient.delete(`/social/comments/${commentId}/`);
}

// ── Share ─────────────────────────────────────────────────────────────────────

export interface LogShareResult {
  /** Fresh share_count after logging. */
  share_count: number;
}

/**
 * POST /api/v1/social/shares/
 *
 * Logs one share audit record and returns the updated share_count.
 * Requires authentication.
 *
 * Call this AFTER the native share / clipboard action succeeds so the
 * count only increments when the user actually shared.
 */
export async function logShare(
  contentType: ContentType,
  contentId: string,
  platform: Platform = "copy_link",
): Promise<LogShareResult> {
  const response = await apiClient.post<LogShareResult>("/social/shares/", {
    content_type: contentType,
    content_id: contentId,
    platform,
  });
  return response.data;
}
