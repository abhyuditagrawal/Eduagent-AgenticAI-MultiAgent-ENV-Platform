"use client";

import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Area,
  AreaChart,
} from "recharts";

interface DailyActivity {
  date: string;
  messages_sent: number;
  concepts_reviewed: number;
  confidence_gained: number;
}

interface ActivityChartProps {
  dailyActivity: DailyActivity[];
}

export function ActivityChart({ dailyActivity }: ActivityChartProps) {
  const data = dailyActivity.map((d) => ({
    date: d.date.slice(5),
    messages: d.messages_sent,
    concepts: d.concepts_reviewed,
  }));

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-muted-foreground">
        No activity data yet
      </div>
    );
  }

  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="colorMessages" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fontSize: 10 }}
            tickLine={false}
            axisLine={false}
          />
          <Legend wrapperStyle={{ fontSize: "11px" }} iconSize={8} />
          <Tooltip
            contentStyle={{
              fontSize: "12px",
              borderRadius: "8px",
              border: "1px solid hsl(var(--border))",
              backgroundColor: "hsl(var(--card))",
            }}
          />
          <Area
            type="monotone"
            dataKey="messages"
            stroke="#3b82f6"
            fill="url(#colorMessages)"
            strokeWidth={2}
            name="Messages"
          />
          <Line
            type="monotone"
            dataKey="concepts"
            stroke="#10b981"
            strokeWidth={2}
            dot={false}
            name="Concepts"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
