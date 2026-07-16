"use client";

import { GraduationCap, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface ProtegeModeIndicatorProps {
  conceptName: string;
  exchangeCount: number;
  maxExchanges: number;
  onEnd: () => void;
}

export function ProtegeModeIndicator({
  conceptName,
  exchangeCount,
  maxExchanges,
  onEnd,
}: ProtegeModeIndicatorProps) {
  const progress = Math.min((exchangeCount / maxExchanges) * 100, 100);

  return (
    <div className="px-4 py-2 border-b bg-green-50/50 dark:bg-green-950/20 flex items-center gap-3">
      <div className="flex items-center gap-2">
        <GraduationCap className="h-4 w-4 text-green-600" />
        <span className="text-sm font-medium text-green-700 dark:text-green-400">
          Teaching Mode
        </span>
      </div>

      <Badge variant="outline" className="text-xs border-green-300 text-green-600">
        {conceptName}
      </Badge>

      <div className="flex-1 flex items-center gap-2">
        <div className="h-1.5 flex-1 max-w-[120px] bg-green-100 dark:bg-green-900 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-500 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="text-xs text-muted-foreground">
          Exchange {exchangeCount}/{maxExchanges}
        </span>
      </div>

      <Button
        variant="ghost"
        size="sm"
        className="h-7 text-xs text-green-600 hover:text-green-700"
        onClick={onEnd}
      >
        End & Evaluate
        <X className="h-3 w-3 ml-1" />
      </Button>
    </div>
  );
}
