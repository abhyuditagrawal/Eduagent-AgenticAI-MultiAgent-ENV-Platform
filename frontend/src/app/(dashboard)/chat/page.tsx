"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { GraduationCap, PanelRightClose, PanelRightOpen } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { MessageBubble } from "@/components/chat/message-bubble";
import { ChatInput } from "@/components/chat/chat-input";
import { AgentTracePanel } from "@/components/chat/agent-trace-panel";
import { SubjectSelector } from "@/components/chat/subject-selector";
import { StreamingIndicator } from "@/components/chat/streaming-indicator";
import { NudgeBanner } from "@/components/nudge-banner";
import { AgentOverrideToolbar } from "@/components/chat/agent-override-toolbar";
import { ConceptPicker } from "@/components/chat/concept-picker";
import { ProtegeModeIndicator } from "@/components/chat/protege-mode-indicator";
import { VivaModeIndicator } from "@/components/chat/viva-mode-indicator";
import { CritiqueUpload } from "@/components/chat/critique-upload";
import { useChatStore } from "@/stores/chat-store";
import { streamChat, type SSEEvent } from "@/lib/sse";
import { toast } from "sonner";

type ActiveMode = "protege" | "viva" | "critique" | null;

interface ModeState {
  mode: ActiveMode;
  conceptName?: string;
  concepts?: string[];
  exchangeCount: number;
  maxExchanges: number;
  questionIndex: number;
  maxQuestions: number;
  difficulty: number;
}

export default function ChatPage() {
  const { data: session } = useSession();
  const {
    activeConversation,
    messages,
    isLoading,
    isStreaming,
    streamingMetadata,
    setActiveConversation,
    addMessage,
    setLoading,
    addConversation,
    startStreaming,
    appendStreamToken,
    updateStreamMetadata,
    finalizeStream,
    cancelStream,
  } = useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const [traceOpen, setTraceOpen] = useState(false);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [agentOverride, setAgentOverride] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Mode-specific state
  const [modeState, setModeState] = useState<ModeState>({
    mode: null,
    exchangeCount: 0,
    maxExchanges: 7,
    questionIndex: 0,
    maxQuestions: 8,
    difficulty: 1,
  });
  const [showConceptPicker, setShowConceptPicker] = useState<"protege" | "viva" | null>(null);

  // Track whether the reader is parked at the bottom. Streaming rewrites the
  // message list on every token, so without this the view would yank back down
  // while they are scrolled up reading earlier answers.
  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    const onScroll = () => {
      const distanceFromBottom =
        viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
      stickToBottomRef.current = distanceFromBottom < 80;
    };

    viewport.addEventListener("scroll", onScroll, { passive: true });
    return () => viewport.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!stickToBottomRef.current) return;
    // Smooth animation per token would fight itself; only the settled view animates.
    messagesEndRef.current?.scrollIntoView({
      behavior: isStreaming ? "auto" : "smooth",
      block: "end",
    });
  }, [messages, isStreaming]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isStreaming) {
        abortRef.current?.abort();
        cancelStream();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isStreaming, cancelStream]);

  // Parse /slash commands from input
  const parseOverride = (content: string): { override: string | null; message: string } => {
    const overrides: Record<string, string> = {
      "/qa": "conceptual_doubt",
      "/exam": "exam_prep",
      "/weak": "weak_points",
      "/teach": "teach_me",
      "/viva": "viva",
      "/critique": "critique",
    };
    for (const [prefix, intent] of Object.entries(overrides)) {
      if (content.startsWith(prefix + " ")) {
        return { override: intent, message: content.slice(prefix.length + 1) };
      }
    }
    return { override: null, message: content };
  };

  // Handle toolbar override change — show concept picker for protege/viva
  const handleOverrideChange = (override: string | null) => {
    setAgentOverride(override);

    if (override === "teach_me") {
      setShowConceptPicker("protege");
    } else if (override === "viva") {
      setShowConceptPicker("viva");
    } else if (override === "critique") {
      setModeState((prev) => ({ ...prev, mode: "critique" }));
    } else {
      // Clear mode if switching away
      if (modeState.mode) {
        setModeState({
          mode: null,
          exchangeCount: 0,
          maxExchanges: 7,
          questionIndex: 0,
          maxQuestions: 8,
          difficulty: 1,
        });
      }
    }
  };

  const handleSend = useCallback(async (rawContent: string) => {
    if (!session?.accessToken) return;

    const { override: slashOverride, message: content } = parseOverride(rawContent);
    const effectiveOverride = slashOverride || agentOverride;

    // Sending is an explicit request to follow along again.
    stickToBottomRef.current = true;

    // Add user message
    const userMessage = {
      id: crypto.randomUUID(),
      role: "user" as const,
      content,
      created_at: new Date().toISOString(),
    };
    addMessage(userMessage);

    // Add placeholder assistant message
    const assistantId = crypto.randomUUID();
    const assistantMessage = {
      id: assistantId,
      role: "assistant" as const,
      content: "",
      created_at: new Date().toISOString(),
    };
    addMessage(assistantMessage);
    startStreaming(assistantId);

    if (!traceOpen) setTraceOpen(true);
    setSelectedMessageId(assistantId);

    try {
      const conversationId = activeConversation?.id || null;

      await streamChat(
        content,
        conversationId,
        selectedSubject,
        effectiveOverride,
        (event: SSEEvent) => {
          switch (event.type) {
            case "token":
              appendStreamToken((event.data.content as string) || "");
              break;
            case "agent_start":
              updateStreamMetadata({
                intent: event.data.intent,
                agent_type: event.data.agent,
              });
              break;
            case "rag_results":
              updateStreamMetadata({
                rag_sources: event.data.sources,
              });
              break;
            case "concept_update":
              updateStreamMetadata({
                confidence_updates: [
                  ...((useChatStore.getState().streamingMetadata.confidence_updates as Array<unknown>) || []),
                  event.data,
                ],
              });
              break;
            case "done": {
              const agentType = (event.data.agent_type as string) || undefined;
              const convId = event.data.conversation_id as string;

              if (!activeConversation && convId) {
                const newConv = {
                  id: convId,
                  title: content.slice(0, 100),
                  agent_type: agentType || null,
                  subject_id: selectedSubject,
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                };
                setActiveConversation(newConv);
                addConversation(newConv);
              }

              // Update mode state for multi-turn agents
              if (agentType === "protege") {
                setModeState((prev) => ({
                  ...prev,
                  mode: "protege",
                  exchangeCount: prev.exchangeCount + 1,
                }));
              } else if (agentType === "viva") {
                setModeState((prev) => ({
                  ...prev,
                  mode: "viva",
                  questionIndex: prev.questionIndex + 1,
                }));
              }

              finalizeStream(agentType);
              break;
            }
            case "error":
              toast.error((event.data.message as string) || "Stream error");
              finalizeStream();
              break;
          }
        }
      );
    } catch (error: unknown) {
      const errMsg =
        error instanceof Error ? error.message : "Failed to send message";
      toast.error(errMsg);
      finalizeStream();
    }
  }, [
    session,
    activeConversation,
    selectedSubject,
    agentOverride,
    traceOpen,
    addMessage,
    startStreaming,
    appendStreamToken,
    updateStreamMetadata,
    finalizeStream,
    setActiveConversation,
    addConversation,
  ]);

  const handleNudgeClick = (nudge: { concept_name: string; subject_id: string }) => {
    if (nudge.subject_id) setSelectedSubject(nudge.subject_id);
    setAgentOverride("weak_points");
    handleSend(`What are my weak points? I need to review ${nudge.concept_name}`);
  };

  const handleEndMode = () => {
    if (modeState.mode === "protege") {
      handleSend("How did I do? Please evaluate my teaching.");
    } else if (modeState.mode === "viva") {
      handleSend("End viva. Please provide my evaluation.");
    }
    setModeState({
      mode: null,
      exchangeCount: 0,
      maxExchanges: 7,
      questionIndex: 0,
      maxQuestions: 8,
      difficulty: 1,
    });
    setAgentOverride(null);
  };

  const handleConceptPickerSelect = (concepts: { id: string; name: string }[]) => {
    setShowConceptPicker(null);

    if (showConceptPicker === "protege" && concepts.length > 0) {
      const concept = concepts[0];
      setModeState((prev) => ({
        ...prev,
        mode: "protege",
        conceptName: concept.name,
        exchangeCount: 0,
      }));
      handleSend(`I want to teach you about "${concept.name}". Let me explain it to you.`);
    } else if (showConceptPicker === "viva") {
      const names = concepts.map((c) => c.name);
      setModeState((prev) => ({
        ...prev,
        mode: "viva",
        concepts: names,
        questionIndex: 0,
      }));
      if (names.length > 0) {
        handleSend(`Start a viva exam covering these topics: ${names.join(", ")}`);
      } else {
        handleSend("Start a viva exam. Choose the topics based on my weakest areas.");
      }
    }
  };

  const handleCritiqueSubmit = (text: string) => {
    setModeState({
      mode: null,
      exchangeCount: 0,
      maxExchanges: 7,
      questionIndex: 0,
      maxQuestions: 8,
      difficulty: 1,
    });
    handleSend(text);
  };

  const streamingAgent = (streamingMetadata?.agent_type as string) || null;
  const isCritiqueMode = modeState.mode === "critique" || agentOverride === "critique";

  return (
    <div className="flex h-full">
      <div className="flex-1 flex flex-col min-w-0">
        {/* Subject selector + trace toggle */}
        <div className="flex items-center justify-between border-b shrink-0">
          <SubjectSelector value={selectedSubject} onChange={setSelectedSubject} />
          <div className="pr-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setTraceOpen(!traceOpen)}
              title={traceOpen ? "Hide agent trace" : "Show agent trace"}
            >
              {traceOpen ? (
                <PanelRightClose className="h-4 w-4" />
              ) : (
                <PanelRightOpen className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>

        {/* Mode indicators */}
        {modeState.mode === "protege" && (
          <ProtegeModeIndicator
            conceptName={modeState.conceptName || "Unknown"}
            exchangeCount={modeState.exchangeCount}
            maxExchanges={modeState.maxExchanges}
            onEnd={handleEndMode}
          />
        )}
        {modeState.mode === "viva" && (
          <VivaModeIndicator
            questionIndex={modeState.questionIndex}
            maxQuestions={modeState.maxQuestions}
            difficulty={modeState.difficulty}
            onEnd={handleEndMode}
          />
        )}

        {/* Nudge Banner */}
        <NudgeBanner onNudgeClick={handleNudgeClick} />

        <ScrollArea className="flex-1 min-h-0" viewportRef={viewportRef}>
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-[60vh] text-center space-y-4">
                <div className="p-4 rounded-full bg-muted">
                  <GraduationCap className="h-12 w-12 text-muted-foreground" />
                </div>
                <div className="space-y-2">
                  <h2 className="text-2xl font-semibold">
                    Welcome to EduAgent
                  </h2>
                  <p className="text-muted-foreground max-w-md">
                    Ask a question about your course material. The AI will
                    automatically route to the right agent and show you the
                    reasoning trace. Use the toolbar below to force a specific agent.
                  </p>
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                id={msg.id}
                role={msg.role}
                content={msg.content}
                agentType={msg.agent_type}
                isSelected={selectedMessageId === msg.id}
                onClick={() => {
                  setSelectedMessageId(msg.id);
                  if (!traceOpen) setTraceOpen(true);
                }}
              />
            ))}

            {isStreaming && (
              <StreamingIndicator agentType={streamingAgent} />
            )}

            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Agent override toolbar */}
        <AgentOverrideToolbar value={agentOverride} onChange={handleOverrideChange} />

        {/* Critique upload or normal chat input */}
        {isCritiqueMode ? (
          <CritiqueUpload
            onSubmit={handleCritiqueSubmit}
            disabled={isLoading || isStreaming}
          />
        ) : (
          <ChatInput onSend={handleSend} disabled={isLoading || isStreaming} />
        )}
      </div>

      {/* Agent Trace Panel */}
      {traceOpen && (
        <AgentTracePanel
          messages={messages}
          selectedMessageId={selectedMessageId}
          onClose={() => setTraceOpen(false)}
        />
      )}

      {/* Concept Picker Modal */}
      {showConceptPicker && (
        <ConceptPicker
          subjectId={selectedSubject}
          mode={showConceptPicker}
          onSelect={handleConceptPickerSelect}
          onClose={() => setShowConceptPicker(null)}
        />
      )}
    </div>
  );
}
