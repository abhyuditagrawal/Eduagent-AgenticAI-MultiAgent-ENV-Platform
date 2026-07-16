import { getSession } from "next-auth/react";

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

export async function streamChat(
  message: string,
  conversationId: string | null,
  subjectId: string | null,
  agentOverride: string | null,
  onEvent: (event: SSEEvent) => void
): Promise<void> {
  await streamSSE(
    "/api/chat/stream",
    {
      message,
      conversation_id: conversationId,
      subject_id: subjectId,
      agent_override: agentOverride,
    },
    onEvent
  );
}

/**
 * Stream a multi-agent debate. Emits debate_start, turn_start, turn, done.
 */
export async function streamDebate(
  question: string,
  subjectId: string | null,
  rounds: number,
  onEvent: (event: SSEEvent) => void
): Promise<void> {
  await streamSSE(
    "/api/debate/stream",
    { question, subject_id: subjectId, rounds },
    onEvent
  );
}

/**
 * Generic Server-Sent-Events POST helper shared by chat and debate.
 */
export async function streamSSE(
  path: string,
  body: Record<string, unknown>,
  onEvent: (event: SSEEvent) => void
): Promise<void> {
  const session = await getSession();
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(session?.accessToken
        ? { Authorization: `Bearer ${session.accessToken}` }
        : {}),
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Stream request failed: ${response.status} ${errorText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events from buffer
      const lines = buffer.split("\n");
      buffer = "";

      let currentEvent = "";
      let currentData = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          currentData = line.slice(6).trim();
        } else if (line === "" && currentEvent && currentData) {
          try {
            const parsed = JSON.parse(currentData);
            onEvent({ type: currentEvent, data: parsed });
          } catch {
            // Skip malformed JSON
          }
          currentEvent = "";
          currentData = "";
        } else if (line !== "") {
          // Incomplete event — put back in buffer
          buffer += line + "\n";
        }
      }

      // If we have an incomplete event at the end, keep it in buffer
      if (currentEvent || currentData) {
        if (currentEvent) buffer += `event: ${currentEvent}\n`;
        if (currentData) buffer += `data: ${currentData}\n`;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
