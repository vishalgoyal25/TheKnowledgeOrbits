/**
 * CA Filter Bar - Date range and source filters
 */

"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Filter } from "lucide-react";

interface CAFilterBarProps {
  onFilterChange: (filters: {
    date_from?: string;
    date_to?: string;
    source_id?: string;
  }) => void;
  sources?: Array<{ id: string; name: string }>;
}

export default function CAFilterBar({
  onFilterChange,
  sources = [],
}: CAFilterBarProps) {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sourceId, setSourceId] = useState("");

  const handleApply = () => {
    onFilterChange({
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      source_id: sourceId || undefined,
    });
  };

  const handleReset = () => {
    setDateFrom("");
    setDateTo("");
    setSourceId("");
    onFilterChange({});
  };

  // Quick filters
  const setLastNDays = (days: number) => {
    const today = new Date();
    const from = new Date(today);
    from.setDate(from.getDate() - days);

    setDateFrom(from.toISOString().split("T")[0]);
    setDateTo(today.toISOString().split("T")[0]);
  };

  return (
    <div className="bg-gray-50 rounded-lg p-4 space-y-4">
      <div className="flex items-center gap-2 mb-2">
        <Filter className="h-4 w-4" />
        <span className="font-medium">Filters</span>
      </div>

      {/* Quick filters */}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={() => setLastNDays(7)}>
          Last 7 days
        </Button>
        <Button variant="outline" size="sm" onClick={() => setLastNDays(30)}>
          Last 30 days
        </Button>
        <Button variant="outline" size="sm" onClick={() => setLastNDays(90)}>
          Last 90 days
        </Button>
      </div>

      {/* Date range */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="date-from">From Date</Label>
          <Input
            id="date-from"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </div>

        <div>
          <Label htmlFor="date-to">To Date</Label>
          <Input
            id="date-to"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>
      </div>

      {/* Source filter */}
      {sources.length > 0 && (
        <div>
          <Label htmlFor="source">Source</Label>
          <select
            id="source"
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
            className="w-full border rounded-md px-3 py-2"
          >
            <option value="">All Sources</option>
            {sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <Button onClick={handleApply} className="flex-1">
          Apply Filters
        </Button>
        <Button variant="outline" onClick={handleReset}>
          Reset
        </Button>
      </div>
    </div>
  );
}
