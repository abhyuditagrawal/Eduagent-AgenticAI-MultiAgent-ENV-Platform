import { create } from "zustand";

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  agent_type?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string | null;
  agent_type: string | null;
  subject_id: string | null;
  created_at: string;
  updated_at: string;
}

interface ChatState {
  conversations: Conversation[];
  activeConversation: Conversation | null;
  messages: Message[];
  isLoading: boolean;
  isStreaming: boolean;
  streamingContent: string;
  streamingMetadata: Record<string, unknown>;
  streamingMessageId: string | null;
  setConversations: (conversations: Conversation[]) => void;
  setActiveConversation: (conversation: Conversation | null) => void;
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  setLoading: (loading: boolean) => void;
  addConversation: (conversation: Conversation) => void;
  startStreaming: (messageId: string) => void;
  appendStreamToken: (token: string) => void;
  updateStreamMetadata: (data: Record<string, unknown>) => void;
  finalizeStream: (agentType?: string) => void;
  cancelStream: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  activeConversation: null,
  messages: [],
  isLoading: false,
  isStreaming: false,
  streamingContent: "",
  streamingMetadata: {},
  streamingMessageId: null,
  setConversations: (conversations) => set({ conversations }),
  setActiveConversation: (activeConversation) => set({ activeConversation }),
  setMessages: (messages) => set({ messages }),
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  setLoading: (isLoading) => set({ isLoading }),
  addConversation: (conversation) =>
    set((state) => ({
      conversations: [conversation, ...state.conversations],
    })),
  startStreaming: (messageId) =>
    set({
      isStreaming: true,
      streamingContent: "",
      streamingMetadata: {},
      streamingMessageId: messageId,
    }),
  appendStreamToken: (token) =>
    set((state) => {
      const newContent = state.streamingContent + token;
      // Update the placeholder message in-place
      const messages = state.messages.map((m) =>
        m.id === state.streamingMessageId
          ? { ...m, content: newContent }
          : m
      );
      return { streamingContent: newContent, messages };
    }),
  updateStreamMetadata: (data) =>
    set((state) => {
      const merged = { ...state.streamingMetadata, ...data };
      const messages = state.messages.map((m) =>
        m.id === state.streamingMessageId
          ? { ...m, metadata: merged, agent_type: (merged.agent_type as string) || m.agent_type }
          : m
      );
      return { streamingMetadata: merged, messages };
    }),
  finalizeStream: (agentType) =>
    set((state) => {
      const messages = state.messages.map((m) =>
        m.id === state.streamingMessageId
          ? {
              ...m,
              content: state.streamingContent,
              metadata: state.streamingMetadata,
              agent_type: agentType || (state.streamingMetadata.agent_type as string) || m.agent_type,
            }
          : m
      );
      return {
        messages,
        isStreaming: false,
        streamingMessageId: null,
      };
    }),
  cancelStream: () =>
    set({ isStreaming: false, streamingMessageId: null }),
}));
