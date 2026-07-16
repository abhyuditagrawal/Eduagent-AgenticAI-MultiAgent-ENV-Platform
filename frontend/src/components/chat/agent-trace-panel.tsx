"use client";

import {
  Brain,
  FileText,
  BookOpen,
  TrendingUp,
  X,
  ChevronRight,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import type { Message } from "@/stores/chat-store";

const AGENT_CONFIG: Record<
  string,
  { label: string; color: string; icon: React.ReactNode }
> = {
  concept_qa: {
    label: "Concept QA",
    color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    icon: <BookOpen className="h-3.5 w-3.5" />,
  },
  exam_predictor: {
    label: "Exam Prep",
    color:
      "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
    icon: <FileText className="h-3.5 w-3.5" />,
  },
  weak_point_tracker: {
    label: "Weak Points",
    color:
      "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
    icon: <TrendingUp className="h-3.5 w-3.5" />,
  },
  protege: {
    label: "Protege",
    color:
      "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    icon: <Brain className="h-3.5 w-3.5" />,
  },
  viva: {
    label: "Viva",
    color: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    icon: <Brain className="h-3.5 w-3.5" />,
  },
  critique: {
    label: "Critique",
    color:
      "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
    icon: <FileText className="h-3.5 w-3.5" />,
  },
  general: {
    label: "General",
    color: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    icon: <Brain className="h-3.5 w-3.5" />,
  },
  simple_rag: {
    label: "RAG",
    color: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    icon: <Brain className="h-3.5 w-3.5" />,
  },
};

interface AgentTracePanelProps {
  messages: Message[];
  selectedMessageId: string | null;
  onClose: () => void;
}

export function AgentTracePanel({
  messages,
  selectedMessageId,
  onClose,
}: AgentTracePanelProps) {
  const assistantMessages = messages.filter((m) => m.role === "assistant");
  const selectedMessage = selectedMessageId
    ? messages.find((m) => m.id === selectedMessageId)
    : assistantMessages[assistantMessages.length - 1];

  const metadata = (selectedMessage?.metadata || {}) as Record<string, unknown>;
  const agentType = (selectedMessage?.agent_type || "unknown") as string;
  const agentConfig = AGENT_CONFIG[agentType] || AGENT_CONFIG.general;

  const intent = metadata.intent as string | undefined;
  const ragSources = (metadata.rag_sources || []) as Array<{
    source_file: string;
    page: number;
    score: number;
  }>;
  const conceptsTouched = (metadata.concepts_touched || []) as string[];
  const confidenceUpdates = (metadata.confidence_updates || []) as Array<{
    concept_id: string;
    quality: number;
  }>;

  return (
    <div className="w-80 border-l bg-card flex flex-col h-full">
      <div className="p-4 flex items-center justify-between border-b">
        <h3 className="font-semibold text-sm">Agent Trace</h3>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-5">
          {!selectedMessage ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              Send a message to see agent trace info
            </p>
          ) : (
            <>
              {/* Intent */}
              <section>
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  Intent Classification
                </h4>
                <Badge variant="secondary" className="text-xs">
                  <ChevronRight className="h-3 w-3 mr-1" />
                  {intent || "N/A"}
                </Badge>
              </section>

              <Separator />

              {/* Agent */}
              <section>
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  Handling Agent
                </h4>
                <Badge className={`text-xs ${agentConfig.color}`}>
                  {agentConfig.icon}
                  <span className="ml-1">{agentConfig.label}</span>
                </Badge>
              </section>

              <Separator />

              {/* Sources */}
              <section>
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  RAG Sources ({ragSources.length})
                </h4>
                {ragSources.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No sources retrieved
                  </p>
                ) : (
                  <div className="space-y-1.5">
                    {ragSources.map((src, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 text-xs p-2 rounded-md bg-muted/50"
                      >
                        <FileText className="h-3.5 w-3.5 mt-0.5 shrink-0 text-muted-foreground" />
                        <div>
                          <p className="font-medium truncate max-w-[180px]">
                            {src.source_file || "Unknown"}
                          </p>
                          <p className="text-muted-foreground">
                            Page {src.page} &middot; Score:{" "}
                            {(src.score * 100).toFixed(0)}%
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <Separator />

              {/* Concepts */}
              <section>
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  Concepts Touched
                </h4>
                {conceptsTouched.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No concepts identified
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {conceptsTouched.map((name, i) => (
                      <Badge key={i} variant="outline" className="text-xs">
                        {name}
                      </Badge>
                    ))}
                  </div>
                )}
              </section>

              <Separator />

              {/* Confidence Updates */}
              <section>
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  Confidence Updates
                </h4>
                {confidenceUpdates.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No updates this turn
                  </p>
                ) : (
                  <div className="space-y-1">
                    {confidenceUpdates.map((u, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between text-xs p-1.5 rounded bg-muted/50"
                      >
                        <span className="truncate max-w-[160px]">
                          {u.concept_id.slice(0, 8)}...
                        </span>
                        <Badge
                          variant="secondary"
                          className={`text-xs ${
                            u.quality >= 3
                              ? "bg-green-100 text-green-700"
                              : "bg-red-100 text-red-700"
                          }`}
                        >
                          q={u.quality}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

export { AGENT_CONFIG };
