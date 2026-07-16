"use client";

import { Badge } from "@/components/ui/badge";
import { Flame, MessageSquare, Brain, Clock } from "lucide-react";

interface DailyActivity {
  date: string;
  messages_sent: number;
  concepts_reviewed: number;
  agents_used: Record<string, number>;
  confidence_gained: number;
  time_spent_minutes: number;
}

interface StreakData {
  current: number;
  longest: number;
  total_days_active: number;
}

interface TotalsData {
  total_messages: number;
  total_concepts_mastered: number;
  total_study_hours: number;
}

interface ActivityTimelineProps {
  dailyActivity: DailyActivity[];
  streak: StreakData;
  totals: TotalsData;
}

export function ActivityTimeline({
  dailyActivity,
  streak,
  totals,
}: ActivityTimelineProps) {
  // Build a 30-day grid (similar to GitHub contribution heatmap)
  const today = new Date();
  const days: { date: string; count: number }[] = [];

  for (let i = 29; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().split("T")[0];
    const activity = dailyActivity.find((a) => a.date === key);
    days.push({
      date: key,
      count: activity?.messages_sent || 0,
    });
  }

  const maxCount = Math.max(...days.map((d) => d.count), 1);

  const getIntensity = (count: number) => {
    if (count === 0) return "bg-muted";
    const ratio = count / maxCount;
    if (ratio > 0.75) return "bg-green-600";
    if (ratio > 0.5) return "bg-green-500";
    if (ratio > 0.25) return "bg-green-400";
    return "bg-green-300";
  };

  return (
    <div className="space-y-4">
      {/* Streak */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <Flame className="h-4 w-4 text-orange-500" />
          <span className="text-lg font-bold">{streak.current}</span>
          <span className="text-xs text-muted-foreground">day streak</span>
        </div>
        <div className="text-xs text-muted-foreground">
          Best: {streak.longest} days
        </div>
      </div>

      {/* Heatmap grid */}
      <div>
        <div className="grid grid-cols-10 gap-1">
          {days.map((day) => (
            <div
              key={day.date}
              className={`w-full aspect-square rounded-sm ${getIntensity(day.count)}`}
              title={`${day.date}: ${day.count} messages`}
            />
          ))}
        </div>
        <div className="flex items-center gap-1 mt-1.5 justify-end">
          <span className="text-[10px] text-muted-foreground">Less</span>
          <div className="w-2.5 h-2.5 rounded-sm bg-muted" />
          <div className="w-2.5 h-2.5 rounded-sm bg-green-300" />
          <div className="w-2.5 h-2.5 rounded-sm bg-green-400" />
          <div className="w-2.5 h-2.5 rounded-sm bg-green-500" />
          <div className="w-2.5 h-2.5 rounded-sm bg-green-600" />
          <span className="text-[10px] text-muted-foreground">More</span>
        </div>
      </div>

      {/* Totals */}
      <div className="grid grid-cols-3 gap-2">
        <div className="text-center p-2 rounded-lg bg-muted/50">
          <MessageSquare className="h-4 w-4 mx-auto text-muted-foreground mb-1" />
          <p className="text-lg font-bold">{totals.total_messages}</p>
          <p className="text-[10px] text-muted-foreground">Messages</p>
        </div>
        <div className="text-center p-2 rounded-lg bg-muted/50">
          <Brain className="h-4 w-4 mx-auto text-muted-foreground mb-1" />
          <p className="text-lg font-bold">{totals.total_concepts_mastered}</p>
          <p className="text-[10px] text-muted-foreground">Mastered</p>
        </div>
        <div className="text-center p-2 rounded-lg bg-muted/50">
          <Clock className="h-4 w-4 mx-auto text-muted-foreground mb-1" />
          <p className="text-lg font-bold">{totals.total_study_hours}</p>
          <p className="text-[10px] text-muted-foreground">Hours</p>
        </div>
      </div>
    </div>
  );
}
