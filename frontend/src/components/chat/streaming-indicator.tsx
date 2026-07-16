"use client";

import { AGENT_CONFIG } from "@/components/chat/agent-trace-panel";

interface StreamingIndicatorProps {
  agentType: string | null;
}

export function StreamingIndicator({ agentType }: StreamingIndicatorProps) {
  const config = agentType ? AGENT_CONFIG[agentType] : null;

  return (
    <div className="flex items-center gap-2 px-4 py-2 text-sm text-muted-foreground">
      <span className="relative flex h-2.5 w-2.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary/60 opacity-75" />
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary" />
      </span>
      {config ? (
        <span className="flex items-center gap-1">
          {config.icon}
          <span>{config.label} is thinking...</span>
        </span>
      ) : (
        <span>Thinking...</span>
      )}
    </div>
  );
}
