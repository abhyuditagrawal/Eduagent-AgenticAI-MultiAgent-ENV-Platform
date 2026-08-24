"use client";

import {
  BookOpen,
  FileText,
  TrendingUp,
  Brain,
  Mic,
  PenLine,
  ChevronDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePersistedState } from "@/lib/use-persisted-state";

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

const TOOLBAR_KEY = "eduagent.toolbar.open";

export function AgentOverrideToolbar({ value, onChange }: AgentOverrideToolbarProps) {
  const [open, setOpen] = usePersistedState(TOOLBAR_KEY, true);

  const toggle = () => setOpen(!open);

  const active = AGENT_BUTTONS.find((b) => b.id === value) ?? AGENT_BUTTONS[0];

  return (
    <div className="border-t bg-muted/30 shrink-0">
      <button
        onClick={toggle}
        className="w-full flex items-center gap-1.5 px-4 py-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
        title={open ? "Hide agent selector" : "Show agent selector"}
      >
        <ChevronDown
          className={`h-3 w-3 transition-transform ${open ? "" : "-rotate-90"}`}
        />
        <span className="font-medium uppercase tracking-wide">Agent</span>
        {!open && (
          <span className="ml-1 flex items-center gap-1 text-foreground">
            {active.icon}
            {active.label}
          </span>
        )}
      </button>

      {open && (
        <div className="flex items-center gap-1 px-4 pb-1.5 overflow-x-auto">
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
      )}
    </div>
  );
}
