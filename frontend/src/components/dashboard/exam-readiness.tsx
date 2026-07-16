"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ExamReadinessProps {
  overallReadiness: number;
  readinessLabel: string;
  byDifficulty: {
    foundational: number;
    intermediate: number;
    advanced: number;
  };
  highRiskTopics: Array<{
    name: string;
    confidence: number;
    difficulty: number;
    impact: string;
  }>;
  strengths: Array<{
    name: string;
    confidence: number;
    difficulty: number;
  }>;
  studyPlan: Array<{
    day: number;
    focus: string;
    duration_hours: number;
    reason: string;
  }>;
  recommendedHours: number;
}

export function ExamReadiness({
  overallReadiness,
  readinessLabel,
  byDifficulty,
  highRiskTopics,
  strengths,
  studyPlan,
  recommendedHours,
}: ExamReadinessProps) {
  const pct = Math.round(overallReadiness * 100);

  const gaugeColor =
    pct >= 80
      ? "text-green-500"
      : pct >= 60
        ? "text-yellow-500"
        : pct >= 40
          ? "text-orange-500"
          : "text-red-500";

  const strokeColor =
    pct >= 80
      ? "#22c55e"
      : pct >= 60
        ? "#eab308"
        : pct >= 40
          ? "#f97316"
          : "#ef4444";

  // SVG circular gauge
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div className="space-y-4">
      {/* Circular gauge */}
      <div className="flex flex-col items-center">
        <div className="relative">
          <svg width="160" height="160" className="-rotate-90">
            <circle
              cx="80"
              cy="80"
              r={radius}
              fill="none"
              stroke="currentColor"
              className="text-muted/30"
              strokeWidth="10"
            />
            <circle
              cx="80"
              cy="80"
              r={radius}
              fill="none"
              stroke={strokeColor}
              strokeWidth="10"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
              className="transition-all duration-1000"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-3xl font-bold ${gaugeColor}`}>{pct}%</span>
            <span className="text-xs text-muted-foreground">{readinessLabel}</span>
          </div>
        </div>
      </div>

      {/* Difficulty breakdown */}
      <div className="space-y-2">
        {(["foundational", "intermediate", "advanced"] as const).map((level) => {
          const val = Math.round((byDifficulty[level] || 0) * 100);
          const colors: Record<string, string> = {
            foundational: "bg-green-500",
            intermediate: "bg-blue-500",
            advanced: "bg-purple-500",
          };
          return (
            <div key={level} className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground w-24 capitalize">{level}</span>
              <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${colors[level]}`}
                  style={{ width: `${val}%` }}
                />
              </div>
              <span className="text-xs font-medium w-10 text-right">{val}%</span>
            </div>
          );
        })}
      </div>

      {/* High risk topics */}
      {highRiskTopics.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground uppercase mb-1.5">High Risk</h4>
          <div className="space-y-1">
            {highRiskTopics.slice(0, 5).map((topic) => (
              <div key={topic.name} className="flex items-center justify-between text-xs">
                <span className="truncate">{topic.name}</span>
                <Badge variant="destructive" className="text-[10px] h-4 ml-2">
                  {Math.round(topic.confidence * 100)}%
                </Badge>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Study plan summary */}
      {studyPlan.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground uppercase mb-1.5">
            Study Plan ({recommendedHours}h total)
          </h4>
          <div className="space-y-1">
            {studyPlan.slice(0, 5).map((item) => (
              <div key={item.day} className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground w-10">Day {item.day}</span>
                <span className="flex-1 truncate">{item.focus}</span>
                <span className="text-muted-foreground">{item.duration_hours}h</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
