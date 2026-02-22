export interface Article {
  id: string;
  title: string;
  slug: string;
  content: string;
  summary: string;
  topic: {
    id: string;
    name: string;
  };
  word_count: number;
  read_time: number;
  created_by: string;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface Bookmark {
  id: string;
  content_type: "article" | "quiz" | "chunk";
  content_id: string;
  notes: string;
  created_at: string;
  // Populated fields (from backend expansion)
  content?: {
    id: string;
    title: string;
    topic?: {
      id: string;
      name: string;
    };
    difficulty_level?: string;
    question_count?: number;
  };
}

export interface Topic {
  id: string;
  name: string;
}
