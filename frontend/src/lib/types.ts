/**
 * TypeScript type definitions for API responses
 */

// Article Types
export interface Article {
  id: string;
  title: string;
  slug: string;
  content: string;
  summary: string;
  topic: Topic;
  word_count: number;
  read_time: number;
  generation_type: 'ai_generated' | 'human_curated' | 'ai_assisted';
  quality_score: number;
  review_status: 'draft' | 'pending' | 'approved' | 'rejected';
  is_published: boolean;
  published_at: string | null;
  source_chunk_count: number;
  static_chunk_count?: number;
  ca_chunk_count?: number;
  created_at: string;
  updated_at: string;
  sources?: ArticleSourceMap[];
}

// Article List Response
export interface ArticleListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Article[];
}

// Source Map Types
export interface ArticleSourceMap {
  id: string;
  chunk: Chunk;
  relevance_weight: number;
  sequence_order: number;
  chunk_contribution: string;
  created_at: string;

  // Flattened fields for UI convenience
  chunk_text?: string;
  source_type?: 'static' | 'dynamic';
  page_number?: number;
  chapter_name?: string;
  article_title?: string;
}

export interface ArticleSourcesResponse {
  article_id: string;
  article_title: string;
  total_sources: number;
  sources: ArticleSourceMap[];
}

// Chunk Types
export interface Chunk {
  id: string;
  chunk_text: string;
  chunk_index: number;
  page_number: number | null;
  source_type: 'static' | 'dynamic';
  document: string;
  document_title: string;
  chapter_name: string;
  quality_flag: 'high' | 'medium' | 'low' | 'needs_review';
  confidence_score: number;
  created_at: string;
}

// Document Types
export interface Document {
  id: string;
  title: string;
  file_path: string;
  source_type: string;
}

// Topic Types
export interface Topic {
  id: string;
  name: string;
  description: string;
  keywords: string[];
  module: string;
  module_name: string;
  subject: string;
  subject_name: string;
  parent_topic: string | null;
  topic_type: 'syllabus' | 'custom';
  difficulty_level: 'easy' | 'medium' | 'hard';
  order_index: number;
  is_active: boolean;
  created_at: string;
}

// Module Types
export interface Module {
  id: string;
  name: string;
  description: string;
  subject: Subject;
  order_index: number;
  is_active: boolean;
}

// Subject Types
export interface Subject {
  id: string;
  name: string;
  description: string;
  program: Program;
  order_index: number;
  is_active: boolean;
}

// Program Types
export interface Program {
  id: string;
  name: string;
  description: string;
  exam_pattern: Record<string, any>;
  is_active: boolean;
}

// Topic List Response
export interface TopicListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Topic[];
}

// Article Generation Request
export interface ArticleGenerationRequest {
  topic_id: string;
  include_ca: boolean;
}

// Article Generation Response
export interface ArticleGenerationResponse {
  message: string;
  article: Article;
  metadata: {
    word_count: number;
    quality_score: number;
    source_chunks: number;
  };
}

// Pagination Params
export interface PaginationParams {
  page?: number;
  page_size?: number;
}

// Filter Params
export interface ArticleFilterParams extends PaginationParams {
  topic_id?: string;
  review_status?: string;
  ordering?: string;
}


/**
 * Current Affairs Types
 */

// CA Source
export interface CASource {
  id: string;
  name: string;
  source_type: string;
  url: string;
  is_active: boolean;
  scrape_frequency: string;
  last_scraped_at: string | null;
  article_count: number;
  created_at: string;
  updated_at: string;
}

// CA Article
export interface CAArticle {
  id: string;
  source: string;
  source_name: string;
  title: string;
  url: string;
  content: string;
  summary: string;
  published_at: string;
  author: string;
  categories: string[];
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  word_count: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

// CA Chunk
export interface CAChunk {
  id: string;
  ca_article: string;
  article_title: string;
  chunk_text: string;
  chunk_index: number;
  source_type: string;
  published_at: string;
  expiry_date: string;
  is_expired: boolean;
  quality_flag: 'high' | 'medium' | 'low' | 'needs_review';
  confidence_score: number;
  topic_count: number;
  created_at: string;
  updated_at: string;
}

// CA Topic Link
export interface CATopicLink {
  id: string;
  ca_chunk: string;
  topic: Topic;
  chunk_text: string;
  article_title: string;
  relevance_score: number;
  link_method: 'auto' | 'manual';
  created_at: string;
}

// List Responses
export interface CAArticleListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: CAArticle[];
}

export interface CAChunkListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: CAChunk[];
}

export interface CASourceListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: CASource[];
}

export interface CATopicLinkListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: CATopicLink[];
}

/**
 * Assessment Engine Types
 * 
 * Complete TypeScript definitions for quiz system.
 */

// ===== Quiz Types =====

export interface Quiz {
  id: string;
  title: string;
  topic: Topic;
  difficulty_level: 'easy' | 'medium' | 'hard';
  include_ca: boolean;
  question_count: number;
  time_limit: number | null;
  is_active: boolean;
  created_at: string;
  questions?: Question[];
}

export interface Question {
  id: string;
  question_text: string;
  question_type: 'single_mcq' | 'multi_statement' | 'assertion_reasoning';
  statements: string[];
  options: {
    A: string;
    B: string;
    C: string;
    D: string;
  };
  correct_answer?: string;  // Only present after submission
  explanation?: string;
  difficulty_level: 'easy' | 'medium' | 'hard';
  order_index: number;
  has_static_sources?: boolean;
  has_ca_sources?: boolean;
}

export interface QuizAttempt {
  id: string;
  quiz: Quiz;
  user: number | null;
  status: 'active' | 'submitted' | 'abandoned' | 'expired';
  score: number | null;
  accuracy: number;
  correct_count: number;
  wrong_count: number;
  unanswered_count: number;
  started_at: string;
  submitted_at: string | null;
  time_spent: number | null;
  responses?: QuestionResponse[];
  questions_with_answers?: Question[];
}

export interface QuestionResponse {
  id: string;
  question: string;
  question_detail?: Question;
  selected_option: string;
  is_correct: boolean;
  time_spent: number;
  marked_for_review: boolean;
  answered_at: string | null;
}

export interface TopicMastery {
  id: string;
  topic: Topic;
  mastery_score: number;
  questions_attempted: number;
  questions_correct: number;
  last_attempted_at: string;
  updated_at: string;
}

// ===== Request/Response Types =====

export interface QuizGenerateRequest {
  topic_id: string;
  difficulty: 'easy' | 'medium' | 'hard';
  include_ca: boolean;
  question_count: number;
}

export interface QuizSubmitRequest {
  attempt_id: string;
  answers: Array<{
    question_id: string;
    selected_option: string;
    time_spent: number;
    marked_for_review?: boolean;
  }>;
}

// ===== UI State Types =====

export interface QuizState {
  currentQuestionIndex: number;
  answers: Record<string, string>;
  questionTimes: Record<string, number>;
  markedForReview: Set<string>;
  visitedQuestions: Set<number>;
}

export interface TimerState {
  timeRemaining: number;
  isRunning: boolean;
  isExpired: boolean;
}

