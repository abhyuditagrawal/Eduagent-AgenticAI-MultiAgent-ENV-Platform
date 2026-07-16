import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "@/stores/chat-store";

describe("Chat Store", () => {
  beforeEach(() => {
    useChatStore.setState({
      conversations: [],
      activeConversation: null,
      messages: [],
      isLoading: false,
      isStreaming: false,
      streamingMessageId: null,
      streamingContent: "",
      streamingMetadata: {},
    });
  });

  it("adds a message", () => {
    const msg = {
      id: "1",
      role: "user" as const,
      content: "Hello",
      created_at: new Date().toISOString(),
    };
    useChatStore.getState().addMessage(msg);
    expect(useChatStore.getState().messages).toHaveLength(1);
    expect(useChatStore.getState().messages[0].content).toBe("Hello");
  });

  it("sets active conversation", () => {
    const conv = {
      id: "conv-1",
      title: "Test",
      agent_type: null,
      subject_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    useChatStore.getState().setActiveConversation(conv);
    expect(useChatStore.getState().activeConversation?.id).toBe("conv-1");
  });

  it("manages streaming state", () => {
    useChatStore.getState().startStreaming("msg-1");
    expect(useChatStore.getState().isStreaming).toBe(true);
    expect(useChatStore.getState().streamingMessageId).toBe("msg-1");

    useChatStore.getState().appendStreamToken("Hello ");
    useChatStore.getState().appendStreamToken("world");
    expect(useChatStore.getState().streamingContent).toBe("Hello world");

    useChatStore.getState().finalizeStream("concept_qa");
    expect(useChatStore.getState().isStreaming).toBe(false);
  });

  it("cancels streaming", () => {
    useChatStore.getState().startStreaming("msg-2");
    useChatStore.getState().appendStreamToken("partial");
    useChatStore.getState().cancelStream();
    expect(useChatStore.getState().isStreaming).toBe(false);
  });

  it("manages conversations list", () => {
    const conv = {
      id: "conv-2",
      title: "Second",
      agent_type: null,
      subject_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    useChatStore.getState().addConversation(conv);
    expect(useChatStore.getState().conversations).toHaveLength(1);
  });

  it("updates streaming metadata", () => {
    useChatStore.getState().startStreaming("msg-3");
    useChatStore.getState().updateStreamMetadata({ intent: "conceptual_doubt" });
    expect(useChatStore.getState().streamingMetadata.intent).toBe("conceptual_doubt");
  });
});
