"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import LineChart from "@/components/charts/LineChart";
import { WeeklyStats } from "@/types/dashboard";

interface Props {
  data: WeeklyStats;
}

export default function PerformanceChart({ data }: Props) {
  if (!data || !data.daily_data || data.daily_data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Weekly Performance</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-[300px] text-muted-foreground border-t border-gray-100 bg-gray-50/50">
          Not enough data yet. Complete some quizzes this week to see your
          progress!
        </CardContent>
      </Card>
    );
  }

  const chartData = data.daily_data.map((d) => ({
    date: new Date(d.date).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
    articles: d.articles,
    quizzes: d.quizzes,
    score: d.avg_score,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Weekly Performance</CardTitle>
        <p className="text-xs text-muted-foreground">
          {data.period} · {data.total_articles} articles · {data.total_quizzes}{" "}
          quizzes
        </p>
      </CardHeader>
      <CardContent>
        <LineChart
          data={chartData}
          xAxisKey="date"
          series={[
            {
              key: "articles",
              name: "Articles",
              color: "#6366f1",
              yAxisId: "left",
            },
            {
              key: "quizzes",
              name: "Quizzes",
              color: "#3b82f6",
              yAxisId: "left",
            },
            {
              key: "score",
              name: "Avg Score %",
              color: "#10b981",
              yAxisId: "right",
            },
          ]}
          height={300}
        />
      </CardContent>
    </Card>
  );
}
