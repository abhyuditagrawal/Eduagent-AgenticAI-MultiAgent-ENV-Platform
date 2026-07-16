"use client";

import { Bot, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import ReactMarkdown from "react-markdown";
import { AGENT_CONFIG } from "@/components/chat/agent-trace-panel";

interface MessageBubbleProps {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  agentType?: string;
  isSelected?: boolean;
  onClick?: () => void;
}

export function MessageBubble({
  id,
  role,
  content,
  agentType,
  isSelected,
  onClick,
}: MessageBubbleProps) {
  const isUser = role === "user";
  const agentConfig = agentType ? AGENT_CONFIG[agentType] : null;

  return (
    <div
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""} ${
        !isUser ? "cursor-pointer" : ""
      } ${isSelected ? "ring-2 ring-primary/30 rounded-2xl p-1 -m-1" : ""}`}
      onClick={!isUser ? onClick : undefined}
    >
      <Avatar className="h-8 w-8 shrink-0 mt-1">
        <AvatarFallback
          className={
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground"
          }
        >
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>

      <div
        className={`flex flex-col gap-1 max-w-[80%] ${
          isUser ? "items-end" : "items-start"
        }`}
      >
        {agentType && !isUser && agentConfig && (
          <Badge className={`text-xs ${agentConfig.color}`}>
            {agentConfig.icon}
            <span className="ml-1">{agentConfig.label}</span>
          </Badge>
        )}

        <div
          className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
            isUser
              ? "bg-primary text-primary-foreground rounded-br-md"
              : "bg-muted rounded-bl-md"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{content}</p>
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
