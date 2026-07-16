"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, X, ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";

interface Nudge {
  type: string;
  concept_name: string;
  concept_id: string;
  subject: string;
  subject_id: string;
  message: string;
  priority: string;
  action: string;
}

interface NudgeBannerProps {
  onNudgeClick?: (nudge: Nudge) => void;
}

export function NudgeBanner({ onNudgeClick }: NudgeBannerProps) {
  const [nudges, setNudges] = useState<Nudge[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadNudges();
  }, []);

  const loadNudges = async () => {
    try {
      const res = await api.get("/api/nudges");
      setNudges(res.data);
    } catch {
      // Silently fail
    }
  };

  const dismiss = (index: number) => {
    setDismissed((prev) => new Set(prev).add(`${index}`));
  };

  const visibleNudges = nudges.filter((_, i) => !dismissed.has(`${i}`));

  if (visibleNudges.length === 0) return null;

  return (
    <div className="space-y-1 px-4 py-2 border-b bg-amber-50/50 dark:bg-amber-950/20">
      {visibleNudges.slice(0, 3).map((nudge, i) => {
        const actualIndex = nudges.indexOf(nudge);
        return (
          <div
            key={actualIndex}
            className="flex items-center gap-2 text-sm"
          >
            <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
            <span className="flex-1 text-muted-foreground truncate">
              {nudge.message}
            </span>
            <Badge
              variant="outline"
              className={`text-xs shrink-0 ${
                nudge.priority === "high"
                  ? "border-red-300 text-red-600"
                  : "border-amber-300 text-amber-600"
              }`}
            >
              {nudge.priority}
            </Badge>
            {onNudgeClick && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0"
                onClick={() => onNudgeClick(nudge)}
              >
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 shrink-0"
              onClick={() => dismiss(actualIndex)}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        );
      })}
    </div>
  );
}
