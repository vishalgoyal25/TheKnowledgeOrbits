import StatsCard from "./StatsCard";
import { BookOpen, Trophy, Flame, TrendingUp } from "lucide-react";

interface Props {
  data: {
    total_articles_read: number;
    total_quizzes_taken: number;
    current_streak: number;
    syllabus_coverage: number;
  };
}

export default function DashboardOverview({ data }: Props) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <StatsCard
        title="Articles Read"
        value={data.total_articles_read}
        icon={<BookOpen className="h-8 w-8 text-blue-600" />}
        color="blue"
      />
      <StatsCard
        title="Quizzes Taken"
        value={data.total_quizzes_taken}
        icon={<Trophy className="h-8 w-8 text-green-600" />}
        color="green"
      />
      <StatsCard
        title="Study Streak"
        value={`${data.current_streak} days`}
        icon={<Flame className="h-8 w-8 text-orange-600" />}
        color="orange"
      />
      <StatsCard
        title="Syllabus Coverage"
        value={`${data.syllabus_coverage.toFixed(1)}%`}
        icon={<TrendingUp className="h-8 w-8 text-purple-600" />}
        color="purple"
      />
    </div>
  );
}
