"use client";

import { Mic, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface VivaModeIndicatorProps {
  questionIndex: number;
  maxQuestions: number;
  difficulty: number;
  onEnd: () => void;
}

export function VivaModeIndicator({
  questionIndex,
  maxQuestions,
  difficulty,
  onEnd,
}: VivaModeIndicatorProps) {
  const diffLabels: Record<number, { label: string; color: string }> = {
    1: { label: "Easy", color: "border-green-300 text-green-600" },
    2: { label: "Medium", color: "border-yellow-300 text-yellow-600" },
    3: { label: "Hard", color: "border-red-300 text-red-600" },
  };

  const diff = diffLabels[difficulty] || diffLabels[1];

  return (
    <div className="px-4 py-2 border-b bg-red-50/50 dark:bg-red-950/20 flex items-center gap-3">
      <div className="flex items-center gap-2">
        <Mic className="h-4 w-4 text-red-600" />
        <span className="text-sm font-medium text-red-700 dark:text-red-400">
          Viva Mode
        </span>
      </div>

      <Badge variant="outline" className="text-xs border-red-300 text-red-600">
        Question {questionIndex + 1} of {maxQuestions}
      </Badge>

      <Badge variant="outline" className={`text-xs ${diff.color}`}>
        {diff.label}
      </Badge>

      <div className="flex-1" />

      <Button
        variant="ghost"
        size="sm"
        className="h-7 text-xs text-red-600 hover:text-red-700"
        onClick={onEnd}
      >
        End Viva
        <X className="h-3 w-3 ml-1" />
      </Button>
    </div>
  );
}
