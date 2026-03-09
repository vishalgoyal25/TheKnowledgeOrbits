/**
 * Shared Engine Stats component
 * Consistent layout for top-level engine pages (Articles, Topics, Quizzes, CA)
 */

interface StatItem {
  label: string;
  value: string | number;
  color: "blue" | "green" | "purple" | "orange";
}

interface EngineStatsProps {
  stats: StatItem[];
}

export function EngineStats({ stats }: EngineStatsProps) {
  const colorMap = {
    blue: "bg-blue-50 text-blue-600",
    green: "bg-green-50 text-green-600",
    purple: "bg-purple-50 text-purple-600",
    orange: "bg-orange-50 text-orange-600",
  };

  return (
    <div
      className={`grid grid-cols-1 md:grid-cols-${Math.min(
        stats.length,
        4,
      )} gap-4 mb-8`}
    >
      {stats.map((stat, idx) => (
        <div
          key={idx}
          className={`${colorMap[stat.color] || colorMap.blue} rounded-lg p-4`}
        >
          <div className="text-sm text-gray-600">{stat.label}</div>
          <div className="text-3xl font-bold">{stat.value}</div>
        </div>
      ))}
    </div>
  );
}
