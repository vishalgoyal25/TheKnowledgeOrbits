/**
 * Quiz Filters Component
 *
 * Filter quizzes by topic, difficulty, CA inclusion.
 */

"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";

/**
 * QuizFiltersProps - Types for the quiz filter component.
 */
interface QuizFiltersProps {
  /** The current active filters state. */
  filters: {
    topic_id: string;
    difficulty: "" | "easy" | "medium" | "hard";
    include_ca: boolean | undefined;
  };
  /** Callback triggered whenever any filter value changes. */
  onFilterChange: (filters: QuizFiltersProps["filters"]) => void;
}

/**
 * QuizFilters component - Provides UI controls to filter the quiz list.
 * Includes topic search, difficulty selection, and a Current Affairs toggle.
 */
export default function QuizFilters({
  filters,
  onFilterChange,
}: QuizFiltersProps) {
  return (
    <Card className="mb-8">
      <CardHeader>
        <CardTitle className="text-lg">Filters</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Topic ID */}
          <div>
            <Label htmlFor="topic">Topic ID (optional)</Label>
            <Input
              id="topic"
              placeholder="Enter topic UUID..."
              value={filters.topic_id}
              onChange={(e) =>
                onFilterChange({ ...filters, topic_id: e.target.value })
              }
            />
          </div>

          {/* Difficulty */}
          <div>
            <Label htmlFor="difficulty">Difficulty</Label>
            <select
              id="difficulty"
              value={filters.difficulty}
              onChange={(e) =>
                onFilterChange({
                  ...filters,
                  difficulty: e.target.value as "easy" | "medium" | "hard" | "",
                })
              }
              className="w-full border rounded-md px-3 py-2 text-sm"
            >
              <option value="">All Levels</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </div>

          {/* Current Affairs Toggle */}
          <div className="flex items-end">
            <div className="flex items-center space-x-2">
              <Switch
                id="include-ca"
                checked={filters.include_ca === true}
                onCheckedChange={(checked) =>
                  onFilterChange({
                    ...filters,
                    include_ca: checked ? true : undefined,
                  })
                }
              />
              <Label htmlFor="include-ca" className="cursor-pointer">
                Current Affairs Only
              </Label>
            </div>
          </div>

          {/* Clear Filters */}
          <div className="flex items-end">
            <button
              onClick={() =>
                onFilterChange({
                  topic_id: "",
                  difficulty: "",
                  include_ca: undefined,
                })
              }
              className="text-sm text-blue-600 hover:underline"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
