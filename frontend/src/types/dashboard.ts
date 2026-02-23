export interface DashboardOverview {
  overview: {
    total_articles_read: number;
    total_quizzes_taken: number;
    current_streak: number;
    syllabus_coverage: number;
  };
  performance: {
    weekly: WeeklyStats;
    topic_count: number;
    average_mastery: number;
  };
  topics: {
    weak: TopicMastery[];
    strong: TopicMastery[];
  };
  recent_activity: Activity[];
  insights: Insight[];
}

export interface WeeklyStats {
  period: string;
  start_date: string;
  end_date: string;
  total_articles: number;
  total_quizzes: number;
  average_score: number;
  daily_data: DailyData[];
}

export interface DailyData {
  date: string;
  articles: number;
  quizzes: number;
  avg_score: number;
}

export interface TopicMastery {
  topic_id: string;
  topic_name: string;
  mastery_score: number;
  questions_attempted: number;
}

export interface Activity {
  event_type: string;
  event_data: Record<string, unknown>;
  created_at: string;
}

export interface Insight {
  type: string;
  data: Record<string, unknown>;
  generated_at: string;
}
