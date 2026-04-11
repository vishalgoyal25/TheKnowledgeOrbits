/**
 * Tags + Concepts Public API — Phase P
 * No auth required. Read-only endpoints.
 */

import apiClient from "./client";
import { DailyCaArticleList } from "./daily-ca";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface TagDetail {
  id: string;
  name: string;
  slug: string;
  description: string;
  tag_type: string;
  usage_count: number;
  is_active: boolean;
  created_at: string;
  recent_articles: { title: string; slug: string }[];
}

export interface TagArticlesResponse {
  tag: string;
  total: number;
  limit: number;
  offset: number;
  results: DailyCaArticleList[];
}

export interface ConceptDetail {
  id: string;
  name: string;
  slug: string;
  brief_description: string;
  body: string | null; // populated only when is_content_ready=true
  is_content_ready: boolean;
  usage_count: number;
  created_at: string;
  linked_articles: { title: string; slug: string }[];
}

// ── API Functions ─────────────────────────────────────────────────────────────

export async function getTagDetail(slug: string): Promise<TagDetail> {
  const res = await apiClient.get(`/tags/${slug}/`);
  return res.data;
}

export async function getTagArticles(
  slug: string,
  limit = 20,
  offset = 0,
): Promise<TagArticlesResponse> {
  const res = await apiClient.get(
    `/tags/${slug}/articles/?limit=${limit}&offset=${offset}`,
  );
  return res.data;
}

export async function getConceptDetail(slug: string): Promise<ConceptDetail> {
  const res = await apiClient.get(`/concepts/${slug}/`);
  return res.data;
}
