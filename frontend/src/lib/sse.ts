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

  /**
   * Parse one complete SSE frame. A frame that carries no data line (a comment
   * or keep-alive) is ignored.
   */
  const emitFrame = (frame: string) => {
    let eventType = "message";
    const dataLines: string[] = [];

    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }

    if (dataLines.length === 0) return;

    try {
      onEvent({ type: eventType, data: JSON.parse(dataLines.join("\n")) });
    } catch {
      // Skip malformed JSON
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // Normalise CRLF so frame splitting works behind proxies that rewrite it.
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

      // Frames are blank-line delimited. A network chunk can split one anywhere,
      // so the trailing segment is always held back until its terminator lands —
      // parsing it early is what used to drop tokens mid-stream.
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        if (frame.trim()) emitFrame(frame);
      }
    }

    // A final frame without its trailing blank line is still a frame.
    if (buffer.trim()) emitFrame(buffer);
  } finally {
    reader.releaseLock();
  }
}
