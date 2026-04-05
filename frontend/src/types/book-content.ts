/**
 * Book Content Engine — TypeScript Types
 * Mirrors the Django serializers in engines/book_content/serializers.py exactly.
 *
 * DO NOT confuse BookContent with Article (article_article — marketing tool).
 * These types represent the 3-Layer Quality Engine output (UPSC book chapters).
 */

// ─────────────────────────────────────────────────────────────────────────────
// SHARED ENUMS / UNION TYPES
// ─────────────────────────────────────────────────────────────────────────────

export type NodeType =
  | "subject_root"
  | "module"
  | "topic"
  | "subtopic"
  | "sub_subtopic";

export type ContentStatus = "empty" | "generating" | "book_quality" | "failed";

export type DifficultyLevel = "easy" | "medium" | "hard";

export type RelationType =
  | "related_to"
  | "prerequisite"
  | "cross_subject"
  | "contrast"
  | "applies_to";

export type RefType = "see_also" | "prerequisite" | "continuation" | "contrast";

export type SourceMode = "wiki_only" | "ncert_wiki";

export type GenerationStatus =
  | "planned"
  | "generating"
  | "partial"
  | "complete"
  | "not_started";

export type LogStatus = "success" | "failed" | "skipped";

// ─────────────────────────────────────────────────────────────────────────────
// BOOK PLAN  (BookPlanSerializer)
// ─────────────────────────────────────────────────────────────────────────────

export interface TocSubtopic {
  name: string;
  prerequisites: string[];
}

export interface TocEntry {
  module: string;
  order: number;
  topics: Array<{
    name: string;
    subtopics: TocSubtopic[];
    prerequisites: string[];
  }>;
}

export interface BookPlan {
  id: string;
  subject_id: string;
  subject_name: string;
  generation_status: GenerationStatus;
  topics_planned: number;
  topics_completed: number;
  avg_quality_score: number;
  completion_pct: number;
  toc_json: TocEntry[];
  reading_order: string[];
  prerequisite_chains: Record<string, string[]>;
  created_at: string;
  updated_at: string;
}

/** Stub returned when no BookPlan exists yet for a subject */
export interface BookPlanStub {
  generation_status: "not_started";
  topics_planned: 0;
  topics_completed: 0;
  avg_quality_score: 0.0;
  completion_pct: 0.0;
}

// ─────────────────────────────────────────────────────────────────────────────
// SUBJECT  (subject_list view response)
// ─────────────────────────────────────────────────────────────────────────────

export interface SubjectWithPlan {
  id: string;
  name: string;
  description: string;
  order_index: number;
  book_plan: BookPlan | BookPlanStub;
}

// ─────────────────────────────────────────────────────────────────────────────
// TOPIC NODE  (TopicNodeSerializer)
// ─────────────────────────────────────────────────────────────────────────────

export interface GraphPosition {
  x: number;
  y: number;
}

export interface TopicNode {
  id: string;
  name: string;
  node_type: NodeType;
  content_status: ContentStatus;
  parent_topic_id: string | null;
  quality_score: number | null;
  /** Reserved for future graph layout engine. Currently always null. */
  graph_position: GraphPosition | null;
  order_index: number;
  difficulty_level: DifficultyLevel;
}

// ─────────────────────────────────────────────────────────────────────────────
// TOPIC RELATION  (TopicRelationSerializer)
// ─────────────────────────────────────────────────────────────────────────────

export interface TopicRelation {
  id: string;
  source_topic_id: string;
  source_topic_name: string;
  target_topic_id: string;
  target_topic_name: string;
  relation_type: RelationType;
  similarity_score: number;
  is_auto_detected: boolean;
  created_at: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// GRAPH DATA  (subject_graph view response)
// ─────────────────────────────────────────────────────────────────────────────

export interface HierarchicalEdge {
  source: string; // source topic UUID
  target: string; // target topic UUID
  type: "contains";
}

export interface GraphEdges {
  hierarchical: HierarchicalEdge[];
  semantic: TopicRelation[];
}

export interface GraphData {
  subject_id: string;
  subject_name: string;
  nodes: TopicNode[];
  edges: GraphEdges;
}

// ─────────────────────────────────────────────────────────────────────────────
// SUBJECT TREE  (subject_tree view response)
// ─────────────────────────────────────────────────────────────────────────────

export interface TreeTopic {
  id: string;
  name: string;
  node_type: NodeType;
  content_status: ContentStatus;
  quality_score: number | null;
  order_index: number;
  difficulty_level: DifficultyLevel;
  subtopics: TreeTopic[]; // recursive
}

export interface TreeModule {
  id: string;
  name: string;
  order_index: number;
  topics: TreeTopic[];
}

export interface SubjectTree {
  id: string;
  name: string;
  modules: TreeModule[];
}

// ─────────────────────────────────────────────────────────────────────────────
// CROSS REFERENCE  (CrossReferenceSerializer)
// ─────────────────────────────────────────────────────────────────────────────

export interface CrossReference {
  id: string;
  target_topic_id: string;
  target_topic_name: string;
  ref_type: RefType;
  ref_text: string;
  display_label: string;
  created_at: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// CONTENT MEDIA  (ContentMediaSerializer)
// ─────────────────────────────────────────────────────────────────────────────

export type MediaType =
  | "image"
  | "diagram"
  | "table_image"
  | "infographic"
  | "video"
  | "placeholder";

export interface ContentMedia {
  id: string;
  media_type: MediaType;
  /** Cloudinary CDN URL — empty string when placeholder not yet fulfilled. */
  cloudinary_url: string;
  /**
   * Exact marker string in content_markdown where this media is inserted.
   * Example: '>[!infographic: Map of British India 1773]<'
   * Frontend matches this against blockquote rawText to resolve the image.
   */
  position_marker: string;
  alt_text: string;
  caption: string;
  display_order: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// BOOK CONTENT — FULL  (BookContentSerializer)
// ─────────────────────────────────────────────────────────────────────────────

export interface BookContent {
  id: string;
  topic_id: string;
  topic_name: string;
  subject_name: string;
  content_markdown: string;
  formatted_content: string;
  /** Use this for rendering — formatted_content if available, else content_markdown */
  render_content: string;
  word_count: number;
  quality_score: number;
  generation_pass: number;
  source_mode: SourceMode;
  has_tables: boolean;
  has_media: boolean;
  is_published: boolean;
  cross_references: CrossReference[];
  /** Cloudinary media assets (images, infographics). Empty array until admin uploads. */
  media_assets: ContentMedia[];
  created_at: string;
  updated_at: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// BOOK CONTENT — LIST  (BookContentListSerializer)
// ─────────────────────────────────────────────────────────────────────────────

export interface BookContentListItem {
  id: string;
  topic_id: string;
  topic_name: string;
  node_type: NodeType;
  word_count: number;
  quality_score: number;
  source_mode: SourceMode;
  has_tables: boolean;
  has_media: boolean;
  is_published: boolean;
  created_at: string;
  updated_at: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// GENERATION LOG  (GenerationLogSerializer)
// ─────────────────────────────────────────────────────────────────────────────

export interface GenerationLog {
  id: string;
  topic_name: string;
  subject_name: string;
  status: LogStatus;
  status_icon: string;
  nodes_created: number;
  relations_created: number;
  cross_refs_created: number;
  quality_score: number;
  word_count: number;
  generation_time_seconds: number;
  error_message: string;
  created_at: string;
}

export interface GenerationLogFilters {
  subject?: string;
  status?: LogStatus;
}
