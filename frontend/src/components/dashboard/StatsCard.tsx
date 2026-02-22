import { ReactNode } from "react";
import { Card } from "@/components/ui/card";

interface Props {
  title: string;
  value: string | number;
  icon: ReactNode;
  color: "blue" | "green" | "orange" | "purple";
}

export default function StatsCard({ title, value, icon, color }: Props) {
  const bgColors = {
    blue: "bg-blue-50",
    green: "bg-green-50",
    orange: "bg-orange-50",
    purple: "bg-purple-50",
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 font-medium">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">{value}</p>
        </div>
        <div className={`p-3 rounded-lg ${bgColors[color]}`}>{icon}</div>
      </div>
    </Card>
  );
}
