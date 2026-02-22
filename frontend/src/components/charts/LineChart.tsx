/**
 * Reusable Line Chart Component using Recharts
 */

"use client";

import React from "react";
import {
  LineChart as ReChartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface DataPoint {
  [key: string]: any;
}

interface Series {
  key: string;
  name: string;
  color: string;
  yAxisId?: string;
}

interface LineChartProps {
  data: DataPoint[];
  xAxisKey: string;
  series: Series[];
  height?: number | string;
  className?: string;
}

export default function LineChart({
  data,
  xAxisKey,
  series,
  height = 300,
  className,
}: LineChartProps) {
  return (
    <div className={className} style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ReChartsLineChart
          data={data}
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            vertical={false}
            stroke="#f0f0f0"
          />
          <XAxis
            dataKey={xAxisKey}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 12, fill: "#6b7280" }}
            dy={10}
          />
          <YAxis
            yAxisId="left"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 12, fill: "#6b7280" }}
          />
          {series.some((s) => s.yAxisId === "right") && (
            <YAxis
              yAxisId="right"
              orientation="right"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 12, fill: "#6b7280" }}
            />
          )}
          <Tooltip
            contentStyle={{
              borderRadius: "8px",
              border: "none",
              boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
            }}
          />
          <Legend wrapperStyle={{ paddingTop: "20px" }} />
          {series.map((s) => (
            <Line
              key={s.key}
              yAxisId={s.yAxisId || "left"}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={s.color}
              strokeWidth={3}
              dot={{ r: 4, strokeWidth: 2, fill: "#fff" }}
              activeDot={{ r: 6, strokeWidth: 0 }}
            />
          ))}
        </ReChartsLineChart>
      </ResponsiveContainer>
    </div>
  );
}
