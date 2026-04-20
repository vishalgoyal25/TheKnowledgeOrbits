/**
 * Daily CA Public API — Phase O
 * No auth required. Public read-only endpoints.
 * Base prefix: /daily-ca/
 */

import apiClient from "./client";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Tag {
  id: string;
  name: string;
  slug: string;
  tag_type: string;
  usage_count: number;
}

export interface ConceptLink {
  id: string;
  name: string;
  slug: string;
  brief_description: string;
  is_content_ready: boolean;
}

export interface DailyCaArticleList {
  id: string;
  slug: string;
  title: string;
  subject_name: string;
  gs_paper: string;
  news_category: string;
  published_date: string;
  news_context: string;
  hero_image_url: string | null;
  quality_score: number;
  order_on_date: number;
  topic_name: string | null;
  tags: Tag[];
}

export interface SourceItem {
  source_name: string;
  url: string;
  title: string;
}

export interface DailyCaArticleDetail extends DailyCaArticleList {
  body_md_processed: string;
  sources_used: SourceItem[];
  is_published: boolean;
  generation_metadata: Record<string, unknown>;
  created_at: string;
  concept_links: ConceptLink[];
  related_articles: DailyCaArticleList[];
  static_background: {
    id: string;
    topic_name: string | null;
    subject_name: string | null;
    word_count: number;
    quality_score: number;
    is_published: boolean;
  } | null;
}

export interface DailyFeedResponse {
  date: string;
  count: number;
  articles: DailyCaArticleList[];
}

export interface ArchiveDay {
  date: string;
  count: number;
  articles: DailyCaArticleList[];
}

export interface ArchiveResponse {
  days: number;
  archive: ArchiveDay[];
}

// ── API Functions ─────────────────────────────────────────────────────────────

export async function getTodayArticles(): Promise<DailyFeedResponse> {
  const res = await apiClient.get("/daily-ca/today/");
  return res.data;
}

export async function getArticlesByDate(
  date: string,
): Promise<DailyFeedResponse> {
  const res = await apiClient.get(`/daily-ca/${date}/`);
  return res.data;
}

export async function getArticleDetail(
  slug: string,
): Promise<DailyCaArticleDetail> {
  const res = await apiClient.get(`/daily-ca/article/${slug}/`);
  return res.data;
}

export async function getArchive(): Promise<ArchiveResponse> {
  const res = await apiClient.get("/daily-ca/archive/");
  return res.data;
}

/**
 * Fetches all article details for a given list of slugs in parallel.
 * Used by the feed to load full bodies after getting the list.
 */
export async function getAllArticleDetails(
  slugs: string[],
): Promise<DailyCaArticleDetail[]> {
  const results = await Promise.allSettled(
    slugs.map((s) => getArticleDetail(s)),
  );
  return results
    .filter(
      (r): r is PromiseFulfilledResult<DailyCaArticleDetail> =>
        r.status === "fulfilled",
    )
    .map((r) => r.value);
}
