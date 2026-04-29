/**
 * RecentActivity Component - Displays a feed of recent user events
 */

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity as ActivityType } from "@/types/dashboard";
import { BookOpen, Trophy, Clock, Newspaper } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

interface RecentActivityProps {
  activities: ActivityType[];
}

export default function RecentActivity({ activities }: RecentActivityProps) {
  const getIcon = (type: string) => {
    switch (type) {
      case "article_read":
        return <BookOpen className="h-4 w-4 text-blue-600" />;
      case "daily_ca_article_read":
        return <Newspaper className="h-4 w-4 text-indigo-600" />;
      case "quiz_completed":
        return <Trophy className="h-4 w-4 text-green-600" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getMessage = (activity: ActivityType) => {
    const data = (activity.event_data as Record<string, unknown>) || {};

    switch (activity.event_type) {
      case "article_read":
        return (
          <p className="text-sm text-gray-700">
            Read{" "}
            <span className="font-semibold">
              {(data.title as string) || "an article"}
            </span>
          </p>
        );
      case "daily_ca_article_read":
        return (
          <p className="text-sm text-gray-700">
            Read Current Affairs —{" "}
            <span className="font-semibold">
              {(data.title as string) || "a CA article"}
            </span>
          </p>
        );
      case "quiz_completed":
        return (
          <p className="text-sm text-gray-700">
            Completed{" "}
            <span className="font-semibold">
              {(data.title as string) || "a quiz"}
            </span>{" "}
            with score{" "}
            <span className="font-bold">{(data.score as number) ?? 0}%</span>
          </p>
        );
      default:
        return <p className="text-sm text-gray-700">Performed an action</p>;
    }
  };

  return (
    <Card className="shadow-sm border-gray-100">
      <CardHeader>
        <CardTitle className="text-xl font-bold">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {activities.length > 0 ? (
          <div className="space-y-6">
            {activities.map((activity, idx) => (
              <div key={idx} className="flex gap-4 relative">
                {idx !== activities.length - 1 && (
                  <div className="absolute left-4 top-8 bottom-[-24px] w-0.5 bg-gray-100" />
                )}
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-50 flex items-center justify-center z-10">
                  {getIcon(activity.event_type)}
                </div>
                <div className="flex-1 pb-2">
                  {getMessage(activity)}
                  <p className="text-xs text-gray-400 mt-1">
                    {formatDistanceToNow(new Date(activity.created_at), {
                      addSuffix: true,
                    })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-10 text-gray-400">
            <p className="text-sm">Start learning to see your activity here!</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
