import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Insight } from "@/types/dashboard";
import {
  Lightbulb,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Info,
} from "lucide-react";

interface Props {
  insights: Insight[];
}

interface InsightStyle {
  bg: string;
  border: string;
  text: string;
  icon: React.ReactNode;
  label: string;
}

function getInsightStyle(type: string): InsightStyle {
  switch (type) {
    case "strength":
      return {
        bg: "bg-green-50",
        border: "border-green-200",
        text: "text-green-800",
        icon: (
          <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0 mt-0.5" />
        ),
        label: "Strength",
      };
    case "warning":
      return {
        bg: "bg-amber-50",
        border: "border-amber-200",
        text: "text-amber-800",
        icon: (
          <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
        ),
        label: "Heads Up",
      };
    case "improvement":
      return {
        bg: "bg-blue-50",
        border: "border-blue-200",
        text: "text-blue-800",
        icon: (
          <TrendingUp className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" />
        ),
        label: "Improve",
      };
    case "tip":
      return {
        bg: "bg-purple-50",
        border: "border-purple-200",
        text: "text-purple-800",
        icon: (
          <Lightbulb className="h-4 w-4 text-purple-500 flex-shrink-0 mt-0.5" />
        ),
        label: "Tip",
      };
    default:
      return {
        bg: "bg-gray-50",
        border: "border-gray-200",
        text: "text-gray-700",
        icon: <Info className="h-4 w-4 text-gray-400 flex-shrink-0 mt-0.5" />,
        label: "Insight",
      };
  }
}

export default function InsightsSection({ insights }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Lightbulb className="h-5 w-5 text-yellow-500" />
          AI Insights
        </CardTitle>
      </CardHeader>
      <CardContent>
        {insights.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-gray-400 gap-2">
            <Lightbulb className="h-8 w-8 text-gray-200" />
            <p className="text-sm text-center">
              No insights yet. Keep studying — they appear after a few sessions!
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {insights.map((insight, idx) => {
              const style = getInsightStyle(insight.type);
              const data = (insight.data as Record<string, unknown>) || {};
              const message =
                (data.message as string) || "New insight available.";
              return (
                <div
                  key={idx}
                  className={`flex gap-3 p-3 rounded-xl border ${style.bg} ${style.border}`}
                >
                  {style.icon}
                  <div className="min-w-0">
                    <p
                      className={`text-[10px] font-bold uppercase tracking-wider mb-0.5 ${style.text} opacity-70`}
                    >
                      {style.label}
                    </p>
                    <p className={`text-sm leading-snug ${style.text}`}>
                      {message}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
