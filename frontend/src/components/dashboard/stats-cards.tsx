/**
 * Dashboard statistics cards
 */

'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileText, BookOpen, TrendingUp, Clock } from 'lucide-react';

interface StatsCardsProps {
  articlesRead?: number;
  totalArticles?: number;
  hoursSpent?: number;
  topicsCompleted?: number;
}

export default function StatsCards({
  articlesRead = 0,
  totalArticles = 0,
  hoursSpent = 0,
  topicsCompleted = 0,
}: StatsCardsProps) {
  const stats = [
    {
      title: 'Articles Read',
      value: articlesRead,
      icon: FileText,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      title: 'Total Articles',
      value: totalArticles,
      icon: BookOpen,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      title: 'Topics Completed',
      value: topicsCompleted,
      icon: TrendingUp,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
    {
      title: 'Hours Spent',
      value: hoursSpent,
      icon: Clock,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
    },
  ];
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {stats.map((stat) => {
        const Icon = stat.icon;
        return (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                {stat.title}
              </CardTitle>
              <div className={`p-2 rounded-lg ${stat.bgColor}`}>
                <Icon className={`h-4 w-4 ${stat.color}`} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{stat.value}</div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
