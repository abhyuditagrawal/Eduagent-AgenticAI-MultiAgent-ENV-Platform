"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useSession } from "next-auth/react";
import {
  Loader2, Users, Plus, Send, LogOut, Bot, MessageSquare,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import api from "@/lib/api";

interface Room {
  id: string;
  name: string;
  subject_id: string | null;
  member_count: number;
  max_members: number;
  created_at: string;
}

interface ChatMessage {
  type: "message" | "system" | "ai_response";
  user_id?: string;
  user_email?: string;
  content: string;
  timestamp: string;
}

export default function StudyGroupsPage() {
  const { data: session } = useSession();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeRoom, setActiveRoom] = useState<Room | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [newRoomName, setNewRoomName] = useState("");
  const [creating, setCreating] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (session?.accessToken) loadRooms();
  }, [session?.accessToken]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadRooms = async () => {
    try {
      const res = await api.get("/api/study-rooms");
      setRooms(res.data);
    } catch {}
    setLoading(false);
  };

  const createRoom = async () => {
    if (!newRoomName.trim()) return;
    setCreating(true);
    try {
      await api.post("/api/study-rooms", { name: newRoomName });
      setNewRoomName("");
      await loadRooms();
    } catch {}
    setCreating(false);
  };

  const joinRoom = async (room: Room) => {
    try {
      await api.post(`/api/study-rooms/${room.id}/join`);
    } catch {}
    connectToRoom(room);
  };

  const connectToRoom = useCallback((room: Room) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    setActiveRoom(room);
    setMessages([]);

    const token = (session as { accessToken?: string })?.accessToken;
    if (!token) return;

    const wsUrl = `${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace("http", "ws")}/ws/study-room/${room.id}?token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setMessages((prev) => [
        ...prev,
        { type: "system", content: "Connected to study room", timestamp: new Date().toISOString() },
      ]);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "history") {
        setMessages(data.messages || []);
      } else {
        setMessages((prev) => [...prev, data]);
      }
    };

    ws.onclose = () => {
      setMessages((prev) => [
        ...prev,
        { type: "system", content: "Disconnected from room", timestamp: new Date().toISOString() },
      ]);
    };

    wsRef.current = ws;
  }, [session]);

  const sendMessage = () => {
    if (!input.trim() || !wsRef.current) return;
    wsRef.current.send(JSON.stringify({ type: "message", content: input }));
    setInput("");
  };

  const askAI = () => {
    if (!input.trim() || !wsRef.current) return;
    wsRef.current.send(JSON.stringify({ type: "ai_question", content: input }));
    setInput("");
  };

  const leaveRoom = async () => {
    if (activeRoom) {
      try {
        await api.post(`/api/study-rooms/${activeRoom.id}/leave`);
      } catch {}
    }
    wsRef.current?.close();
    setActiveRoom(null);
    setMessages([]);
    await loadRooms();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Active room view
  if (activeRoom) {
    return (
      <div className="flex flex-col h-full">
        <div className="border-b px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            <h2 className="font-semibold">{activeRoom.name}</h2>
          </div>
          <Button variant="ghost" size="sm" onClick={leaveRoom}>
            <LogOut className="h-4 w-4 mr-1" /> Leave
          </Button>
        </div>

        <ScrollArea className="flex-1 p-4">
          <div className="space-y-3">
            {messages.map((msg, i) => (
              <div key={i} className={`${
                msg.type === "system" ? "text-center text-xs text-muted-foreground" :
                msg.type === "ai_response" ? "flex justify-start" : "flex justify-start"
              }`}>
                {msg.type === "system" ? (
                  <span>{msg.content}</span>
                ) : msg.type === "ai_response" ? (
                  <div className="max-w-[80%] bg-primary/10 rounded-lg px-4 py-2">
                    <p className="text-xs font-medium text-primary mb-1 flex items-center gap-1">
                      <Bot className="h-3 w-3" /> EduAgent AI
                    </p>
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  </div>
                ) : (
                  <div className="max-w-[80%] bg-muted rounded-lg px-4 py-2">
                    <p className="text-xs font-medium text-muted-foreground mb-1">
                      {msg.user_email}
                    </p>
                    <p className="text-sm">{msg.content}</p>
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        <div className="border-t p-4 flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message..."
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
          />
          <Button size="icon" onClick={sendMessage}>
            <Send className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="secondary" onClick={askAI} title="Ask AI">
            <Bot className="h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  }

  // Room list view
  return (
    <div className="flex flex-col h-full overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Users className="h-6 w-6" /> Study Groups
        </h1>
      </div>

      {/* Create room */}
      <Card>
        <CardContent className="pt-6 flex gap-2">
          <Input
            value={newRoomName}
            onChange={(e) => setNewRoomName(e.target.value)}
            placeholder="Room name..."
            onKeyDown={(e) => e.key === "Enter" && createRoom()}
          />
          <Button onClick={createRoom} disabled={creating || !newRoomName.trim()}>
            <Plus className="h-4 w-4 mr-1" /> Create Room
          </Button>
        </CardContent>
      </Card>

      {/* Room list */}
      {rooms.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-center text-muted-foreground">
          <div>
            <Users className="h-12 w-12 mx-auto mb-4 opacity-30" />
            <p className="text-lg font-medium">No study rooms yet</p>
            <p className="text-sm">Create a room and invite classmates to study together.</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rooms.map((room) => (
            <Card key={room.id} className="hover:shadow-md transition-shadow cursor-pointer">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <MessageSquare className="h-4 w-4" />
                  {room.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground mb-3">
                  {room.member_count}/{room.max_members} members
                </p>
                <Button
                  size="sm"
                  className="w-full"
                  onClick={() => joinRoom(room)}
                >
                  Join Room
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
