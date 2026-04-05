/**
 * Book Content Engine — API Client
 * Typed wrappers over the Part 5 DRF endpoints.
 *
 * Base prefix: /book/  (registered in core/urls.py)
 * All endpoints require a valid JWT (Bearer token via apiClient interceptor).
 * generation-log endpoint additionally requires is_staff.
 */

import {
  BookContent,
  GenerationLog,
  GenerationLogFilters,
  GraphData,
  SubjectTree,
  SubjectWithPlan,
  TopicNode,
  CrossReference,
} from "@/types/book-content";
import apiClient from "./client";

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/v1/book/subjects/
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Returns all active subjects enriched with their BookPlan status.
 * Used by: subject selector dropdown on /knowledge page.
 */
export async function getBookSubjects(): Promise<SubjectWithPlan[]> {
  const response = await apiClient.get("/book/subjects/");
  return response.data;
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/v1/book/tree/{subject_id}/
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Returns the full subject → module → topic → subtopic hierarchy.
 * Used by: hamburger/navbar outline view on /knowledge page.
 */
export async function getBookTree(subjectId: string): Promise<SubjectTree> {
  const response = await apiClient.get(`/book/tree/${subjectId}/`);
  return response.data;
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/v1/book/graph/{subject_id}/
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Returns ALL topic nodes + hierarchical and semantic edges for D3.js.
 * Used by: Knowledge Graph UI (eye/graph toggle view).
 */
export async function getBookGraph(subjectId: string): Promise<GraphData> {
  const response = await apiClient.get(`/book/graph/${subjectId}/`);
  return response.data;
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/v1/book/graph/{subject_id}/node/{topic_id}/children/
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Returns ONLY the direct children of a topic node.
 * Called on single-click of a collapsed node for progressive disclosure.
 * Used by: Knowledge Graph UI (lazy-load on node click).
 */
export async function getGraphNodeChildren(
  subjectId: string,
  topicId: string,
): Promise<TopicNode[]> {
  const response = await apiClient.get(
    `/book/graph/${subjectId}/node/${topicId}/children/`,
  );
  return response.data;
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/v1/book/content/{topic_id}/
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Returns full BookContent for a topic — markdown, quality score, cross-refs.
 * Always use `render_content` field for display (pre-resolved by backend).
 * Used by: article reader panel in both navbar and graph UI.
 */
export async function getBookContent(topicId: string): Promise<BookContent> {
  const response = await apiClient.get(`/book/content/${topicId}/`);
  return response.data;
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/v1/book/content/{topic_id}/cross-references/
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Returns all outgoing CrossReference records for an article.
 * Dedicated endpoint so See Also loads independently without re-fetching markdown.
 * Used by: See Also section in article reader.
 */
export async function getCrossReferences(
  topicId: string,
): Promise<CrossReference[]> {
  const response = await apiClient.get(
    `/book/content/${topicId}/cross-references/`,
  );
  return response.data;
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/v1/book/generation-log/   (staff only)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Returns recent GenerationLog records for the admin monitoring dashboard.
 * Supports optional subject and status filters.
 * Requires is_staff — will 403 for non-staff users.
 */
export async function getGenerationLog(
  filters?: GenerationLogFilters,
): Promise<GenerationLog[]> {
  const response = await apiClient.get("/book/generation-log/", {
    params: filters,
  });
  return response.data;
}
