"use client";

import { useRouter } from "next/navigation";
import { AlertTriangle, BookOpen, FileText, GraduationCap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface WeakConcept {
  concept: { id: string; name: string; chapter: string };
  confidence: number;
  reason: string;
  missing_prerequisites: string[];
  suggestion: string;
  priority: string;
}

interface WeakPointsListProps {
  weakConcepts: WeakConcept[];
  totalWeak: number;
  totalConcepts: number;
}

const REASON_ICONS: Record<string, React.ReactNode> = {
  prerequisite_gap: <AlertTriangle className="h-3.5 w-3.5 text-red-500" />,
  low_confidence: <AlertTriangle className="h-3.5 w-3.5 text-orange-500" />,
  overdue_review: <AlertTriangle className="h-3.5 w-3.5 text-yellow-500" />,
};

const PRIORITY_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  medium: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  low: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
};

export function WeakPointsList({
  weakConcepts,
  totalWeak,
  totalConcepts,
}: WeakPointsListProps) {
  const router = useRouter();

  const navigateToChat = (conceptName: string, override: string) => {
    router.push(
      `/chat?override=${override}&concept=${encodeURIComponent(conceptName)}`
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {totalWeak} weak of {totalConcepts} concepts
        </span>
      </div>

      <div className="space-y-2">
        {weakConcepts.slice(0, 8).map((item) => (
          <div
            key={item.concept.id}
            className="border rounded-lg p-3 space-y-2"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-1.5 min-w-0">
                {REASON_ICONS[item.reason] || REASON_ICONS.low_confidence}
                <span className="text-sm font-medium truncate">
                  {item.concept.name}
                </span>
              </div>
              <Badge
                className={`text-[10px] shrink-0 ${PRIORITY_COLORS[item.priority] || PRIORITY_COLORS.medium}`}
              >
                {item.priority}
              </Badge>
            </div>

            {item.concept.chapter && (
              <p className="text-xs text-muted-foreground">{item.concept.chapter}</p>
            )}

            {/* Confidence bar */}
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-orange-500 rounded-full"
                  style={{ width: `${Math.round(item.confidence * 100)}%` }}
                />
              </div>
              <span className="text-xs text-muted-foreground w-8 text-right">
                {Math.round(item.confidence * 100)}%
              </span>
            </div>

            <p className="text-xs text-muted-foreground">{item.suggestion}</p>

            <div className="flex gap-1.5">
              <Button
                size="sm"
                variant="outline"
                className="h-6 text-[11px] px-2"
                onClick={() => navigateToChat(item.concept.name, "conceptual_doubt")}
              >
                <BookOpen className="h-3 w-3 mr-1" />
                Review
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-6 text-[11px] px-2"
                onClick={() => navigateToChat(item.concept.name, "exam_prep")}
              >
                <FileText className="h-3 w-3 mr-1" />
                Practice
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-6 text-[11px] px-2"
                onClick={() => navigateToChat(item.concept.name, "teach_me")}
              >
                <GraduationCap className="h-3 w-3 mr-1" />
                Teach
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
