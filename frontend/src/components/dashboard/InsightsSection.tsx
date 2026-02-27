import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Insight } from "@/types/dashboard";
import { Lightbulb } from "lucide-react";

interface Props {
  insights: Insight[];
}

export default function InsightsSection({ insights }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Lightbulb className="h-5 w-5 text-yellow-600" />
          Insights
        </CardTitle>
      </CardHeader>
      <CardContent>
        {insights.length === 0 ? (
          <p className="text-gray-500">No insights yet. Keep studying!</p>
        ) : (
          <div className="space-y-3">
            {insights.map((insight, idx) => {
              const data = (insight.data as Record<string, unknown>) || {};
              return (
                <Alert key={idx} className="bg-blue-50 border-blue-200">
                  <AlertDescription className="text-sm">
                    {(data.message as string) || "New insight available"}
                  </AlertDescription>
                </Alert>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
