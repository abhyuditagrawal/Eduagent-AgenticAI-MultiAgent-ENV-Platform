"use client";

import { BookOpen, FileText, TrendingUp, Brain, Mic, PenLine } from "lucide-react";
import { Button } from "@/components/ui/button";

interface AgentOverrideToolbarProps {
  value: string | null;
  onChange: (override: string | null) => void;
}

const AGENT_BUTTONS = [
  { id: null, label: "Auto", icon: <Brain className="h-3.5 w-3.5" />, disabled: false },
  { id: "conceptual_doubt", label: "QA", icon: <BookOpen className="h-3.5 w-3.5" />, disabled: false },
  { id: "exam_prep", label: "Exam", icon: <FileText className="h-3.5 w-3.5" />, disabled: false },
  { id: "weak_points", label: "Weak Points", icon: <TrendingUp className="h-3.5 w-3.5" />, disabled: false },
  { id: "teach_me", label: "Protege", icon: <Brain className="h-3.5 w-3.5" />, disabled: false },
  { id: "viva", label: "Viva", icon: <Mic className="h-3.5 w-3.5" />, disabled: false },
  { id: "critique", label: "Critique", icon: <PenLine className="h-3.5 w-3.5" />, disabled: false },
] as const;

export function AgentOverrideToolbar({ value, onChange }: AgentOverrideToolbarProps) {
  return (
    <div className="flex items-center gap-1 px-4 py-1.5 border-t bg-muted/30 overflow-x-auto">
      {AGENT_BUTTONS.map((btn) => {
        const isActive = btn.id === value;
        return (
          <Button
            key={btn.id ?? "auto"}
            variant={isActive ? "default" : "ghost"}
            size="sm"
            className={`h-7 text-xs gap-1 shrink-0 ${
              isActive ? "ring-2 ring-primary/30" : ""
            }`}
            disabled={btn.disabled}
            onClick={() => onChange(btn.id)}
          >
            {btn.icon}
            {btn.label}
          </Button>
        );
      })}
    </div>
  );
}
