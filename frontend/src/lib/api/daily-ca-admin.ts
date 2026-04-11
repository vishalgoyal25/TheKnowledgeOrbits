/**
 * Daily CA Admin API — Phase N
 * No auth required (solo developer).
 * Base prefix: /admin/daily-ca/
 */

import apiClient from "./client";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Proposal {
  id: string;
  title: string;
  description: string;
  topic_name: string | null;
  subject_name: string;
  gs_paper: string;
  relevance_score: number;
  source_count: number;
  status:
    | "pending"
    | "approved"
    | "rejected"
    | "generated"
    | "failed"
    | "queued_next_run";
  approved_at: string | null;
  date: string;
}

export interface ProposalListResponse {
  date: string;
  count: number;
  proposals: Proposal[];
}

export interface ApproveResponse {
  approved: number;
  requested: number;
}

export interface GenerateStatusResponse {
  date: string;
  total: number;
  status_breakdown: Record<string, number>;
  generation_complete: boolean;
  articles_generated: number;
}

export interface AdminArticle {
  id: string;
  slug: string;
  title: string;
  subject_name: string;
  gs_paper: string;
  published_date: string;
  news_context: string;
  hero_image_url: string;
  body_md_processed: string;
  quality_score: number;
  order_on_date: number;
  is_published: boolean;
  generation_metadata: Record<string, unknown>;
  tags: {
    id: string;
    name: string;
    slug: string;
    tag_type: string;
    usage_count: number;
  }[];
  concept_links: {
    id: string;
    name: string;
    slug: string;
    brief_description: string;
    is_content_ready: boolean;
  }[];
  topic_name: string | null;
}

export interface AdminArticlesResponse {
  date: string;
  count: number;
  articles: AdminArticle[];
}

// ── API Functions ─────────────────────────────────────────────────────────────

export async function getProposals(
  date: string,
): Promise<ProposalListResponse> {
  const res = await apiClient.get(`/admin/daily-ca/proposals/${date}/`);
  return res.data;
}

export async function approveProposals(
  proposalIds: string[],
): Promise<ApproveResponse> {
  const res = await apiClient.post("/admin/daily-ca/proposals/approve/", {
    proposal_ids: proposalIds,
  });
  return res.data;
}

export async function getGenerateStatus(
  date: string,
): Promise<GenerateStatusResponse> {
  const res = await apiClient.get(
    `/admin/daily-ca/generate/status/?date=${date}`,
  );
  return res.data;
}

export async function publishDate(
  date: string,
): Promise<{ date: string; published: number }> {
  const res = await apiClient.post(`/admin/daily-ca/publish/${date}/`);
  return res.data;
}

export async function getAdminArticles(
  date: string,
): Promise<AdminArticlesResponse> {
  const res = await apiClient.get(`/admin/daily-ca/articles/${date}/`);
  return res.data;
}

export async function triggerGeneration(
  date: string,
): Promise<{ status: string; date: string }> {
  const res = await apiClient.post("/admin/daily-ca/generate/run/", { date });
  return res.data;
}
