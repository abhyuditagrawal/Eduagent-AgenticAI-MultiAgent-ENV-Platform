"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useSession } from "next-auth/react";
import {
  Loader2, Users, Plus, Send, LogOut, Bot, MessageSquare, Eraser, Swords, Gavel, StickyNote, Trash2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

interface StrokePoint {
  x: number;
  y: number;
}

interface Stroke {
  user_id: string;
  stroke: { points: StrokePoint[]; color: string; width: number };
  timestamp: string;
}

interface PeerDebateArgument {
  name: string;
  content: string;
}

interface PeerDebateState {
  topic: string;
  subject_code?: string | null;
  subject_name?: string | null;
  arguments: Record<string, PeerDebateArgument>;
  verdict: string | null;
  started_by: string;
}

interface Annotation {
  id: string;
  source_file: string;
  page: number;
  note: string;
  highlight_text: string | null;
  author_name: string;
  created_at: string;
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

  // Whiteboard (Future Work item #3)
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawingRef = useRef(false);
  const currentStrokeRef = useRef<StrokePoint[]>([]);
  const [strokes, setStrokes] = useState<Stroke[]>([]);

  // Peer debate (Future Work item #8)
  const [debate, setDebate] = useState<PeerDebateState | null>(null);
  const [debateTopic, setDebateTopic] = useState("");
  const [debateArgument, setDebateArgument] = useState("");
  const [judging, setJudging] = useState(false);

  // Collaborative material annotations (Future Work item #9)
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [noteFile, setNoteFile] = useState("");
  const [notePage, setNotePage] = useState("1");
  const [noteText, setNoteText] = useState("");

  useEffect(() => {
    if (session?.accessToken) loadRooms();
  }, [session?.accessToken]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Redraw the whole whiteboard whenever the stroke log changes (new stroke,
  // history replay on join, or a clear). Simpler and less error-prone than
  // incremental canvas patching for a live collaborative surface.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const s of strokes) {
      const pts = s.stroke.points;
      if (!pts || pts.length < 2) continue;
      ctx.beginPath();
      ctx.strokeStyle = s.stroke.color || "#111827";
      ctx.lineWidth = s.stroke.width || 2;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.moveTo(pts[0].x, pts[0].y);
      for (const p of pts.slice(1)) ctx.lineTo(p.x, p.y);
      ctx.stroke();
    }
  }, [strokes]);

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
    setStrokes([]);
    setDebate(null);
    setAnnotations([]);
    if (room.subject_id) loadAnnotations(room.subject_id);

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
      switch (data.type) {
        case "history":
          setMessages(data.messages || []);
          break;
        case "whiteboard_history":
          setStrokes(data.strokes || []);
          break;
        case "whiteboard_draw":
          setStrokes((prev) => [...prev, { user_id: data.user_id, stroke: data.stroke, timestamp: data.timestamp }]);
          break;
        case "whiteboard_clear":
          setStrokes([]);
          break;
        case "debate_state":
          setDebate(data.debate);
          break;
        case "debate_verdict":
          setDebate(data.debate);
          setJudging(false);
          break;
        case "annotation":
          if (data.annotation) {
            setAnnotations((prev) =>
              prev.some((a) => a.id === data.annotation.id) ? prev : [data.annotation, ...prev]
            );
          }
          break;
        default:
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

  const getCanvasPoint = (e: React.MouseEvent<HTMLCanvasElement>): StrokePoint => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const handleCanvasMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    drawingRef.current = true;
    currentStrokeRef.current = [getCanvasPoint(e)];
  };

  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current) return;
    currentStrokeRef.current.push(getCanvasPoint(e));
    // Live-preview the in-progress stroke locally without spamming the
    // network - the final stroke is broadcast once on mouse-up.
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!ctx) return;
    const pts = currentStrokeRef.current;
    if (pts.length < 2) return;
    ctx.beginPath();
    ctx.strokeStyle = "#111827";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.moveTo(pts[pts.length - 2].x, pts[pts.length - 2].y);
    ctx.lineTo(pts[pts.length - 1].x, pts[pts.length - 1].y);
    ctx.stroke();
  };

  const handleCanvasMouseUp = () => {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    const points = currentStrokeRef.current;
    currentStrokeRef.current = [];
    if (points.length < 2 || !wsRef.current) return;
    const stroke = { points, color: "#111827", width: 2 };
    setStrokes((prev) => [...prev, { user_id: "me", stroke, timestamp: new Date().toISOString() }]);
    wsRef.current.send(JSON.stringify({ type: "whiteboard_draw", stroke }));
  };

  const loadAnnotations = async (subjectId: string) => {
    try {
      const res = await api.get(`/api/annotations?subject_id=${subjectId}`);
      setAnnotations(res.data);
    } catch {}
  };

  const submitAnnotation = async () => {
    if (!noteText.trim() || !noteFile.trim() || !activeRoom?.subject_id) return;
    try {
      const res = await api.post("/api/annotations", {
        subject_id: activeRoom.subject_id,
        source_file: noteFile,
        page: parseInt(notePage, 10) || 0,
        note: noteText,
        room_id: activeRoom.id,
      });
      setAnnotations((prev) => [res.data, ...prev]);
      wsRef.current?.send(JSON.stringify({ type: "annotation", annotation: res.data }));
      setNoteText("");
    } catch {}
  };

  const removeAnnotation = async (id: string) => {
    try {
      await api.delete(`/api/annotations/${id}`);
      setAnnotations((prev) => prev.filter((a) => a.id !== id));
    } catch {}
  };

  const clearWhiteboard = () => {
    setStrokes([]);
    wsRef.current?.send(JSON.stringify({ type: "whiteboard_clear" }));
  };

  const startDebate = () => {
    if (!debateTopic.trim() || !wsRef.current) return;
    wsRef.current.send(JSON.stringify({
      type: "debate_start",
      topic: debateTopic,
      subject_code: activeRoom?.subject_id,
    }));
    setDebateTopic("");
  };

  const sendDebateArgument = () => {
    if (!debateArgument.trim() || !wsRef.current) return;
    wsRef.current.send(JSON.stringify({ type: "debate_argument", content: debateArgument }));
    setDebateArgument("");
  };

  const requestVerdict = () => {
    if (!wsRef.current) return;
    setJudging(true);
    wsRef.current.send(JSON.stringify({ type: "debate_judge" }));
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

        <Tabs defaultValue="chat" className="flex-1 min-h-0 flex flex-col">
          <div className="border-b px-4 pt-2">
            <TabsList>
              <TabsTrigger value="chat">
                <MessageSquare className="h-3.5 w-3.5 mr-1" /> Chat
              </TabsTrigger>
              <TabsTrigger value="whiteboard">Whiteboard</TabsTrigger>
              <TabsTrigger value="debate">
                <Swords className="h-3.5 w-3.5 mr-1" /> Peer Debate
              </TabsTrigger>
              <TabsTrigger value="notes">
                <StickyNote className="h-3.5 w-3.5 mr-1" /> Notes
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="chat" className="flex-1 min-h-0 flex flex-col">
            <ScrollArea className="flex-1 min-h-0 p-4">
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
          </TabsContent>

          <TabsContent value="whiteboard" className="flex-1 min-h-0 flex flex-col p-4 gap-2">
            <div className="flex justify-between items-center">
              <p className="text-xs text-muted-foreground">
                Draw together in real time - everyone in the room sees your strokes live.
              </p>
              <Button size="sm" variant="outline" onClick={clearWhiteboard}>
                <Eraser className="h-3.5 w-3.5 mr-1" /> Clear
              </Button>
            </div>
            <canvas
              ref={canvasRef}
              width={900}
              height={480}
              className="border rounded-md bg-white cursor-crosshair w-full max-w-full touch-none"
              onMouseDown={handleCanvasMouseDown}
              onMouseMove={handleCanvasMouseMove}
              onMouseUp={handleCanvasMouseUp}
              onMouseLeave={handleCanvasMouseUp}
            />
          </TabsContent>

          <TabsContent value="debate" className="flex-1 min-h-0 overflow-auto p-4 space-y-4">
            {!debate ? (
              <div className="max-w-md space-y-2">
                <p className="text-sm text-muted-foreground">
                  Start a peer debate: propose a topic, everyone submits their position,
                  then ask the AI to moderate.
                </p>
                <div className="flex gap-2">
                  <Input
                    value={debateTopic}
                    onChange={(e) => setDebateTopic(e.target.value)}
                    placeholder="Debate topic or question..."
                    onKeyDown={(e) => e.key === "Enter" && startDebate()}
                  />
                  <Button onClick={startDebate} disabled={!debateTopic.trim()}>
                    Start
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4 max-w-2xl">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Swords className="h-4 w-4" /> {debate.topic}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {Object.entries(debate.arguments).length === 0 ? (
                      <p className="text-xs text-muted-foreground">No positions submitted yet.</p>
                    ) : (
                      Object.entries(debate.arguments).map(([uid, arg]) => (
                        <div key={uid} className="bg-muted rounded-lg px-3 py-2">
                          <p className="text-xs font-medium text-muted-foreground mb-1">{arg.name}</p>
                          <p className="text-sm">{arg.content}</p>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>

                <div className="flex gap-2">
                  <Input
                    value={debateArgument}
                    onChange={(e) => setDebateArgument(e.target.value)}
                    placeholder="State your position..."
                    onKeyDown={(e) => e.key === "Enter" && sendDebateArgument()}
                  />
                  <Button onClick={sendDebateArgument} disabled={!debateArgument.trim()}>
                    Submit
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={requestVerdict}
                    disabled={judging || Object.keys(debate.arguments).length === 0}
                  >
                    {judging ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <><Gavel className="h-4 w-4 mr-1" /> AI Verdict</>
                    )}
                  </Button>
                </div>

                {debate.verdict && (
                  <Card className="bg-primary/5">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <Gavel className="h-4 w-4" /> Moderator's Verdict
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm whitespace-pre-wrap">{debate.verdict}</p>
                    </CardContent>
                  </Card>
                )}
              </div>
            )}
          </TabsContent>

          <TabsContent value="notes" className="flex-1 min-h-0 overflow-auto p-4 space-y-4">
            {!activeRoom.subject_id ? (
              <p className="text-sm text-muted-foreground">
                This room isn't linked to a subject, so shared notes aren't available here.
              </p>
            ) : (
              <div className="max-w-2xl space-y-4">
                <p className="text-xs text-muted-foreground">
                  Pin a note to a page of the subject's material - it's saved for everyone,
                  not just this session.
                </p>
                <Card>
                  <CardContent className="pt-4 space-y-2">
                    <div className="flex gap-2">
                      <Input
                        value={noteFile}
                        onChange={(e) => setNoteFile(e.target.value)}
                        placeholder="File name (e.g. chapter1.pdf)"
                        className="flex-1"
                      />
                      <Input
                        value={notePage}
                        onChange={(e) => setNotePage(e.target.value)}
                        placeholder="Page"
                        type="number"
                        className="w-20"
                      />
                    </div>
                    <div className="flex gap-2">
                      <Input
                        value={noteText}
                        onChange={(e) => setNoteText(e.target.value)}
                        placeholder="Your note..."
                        onKeyDown={(e) => e.key === "Enter" && submitAnnotation()}
                      />
                      <Button onClick={submitAnnotation} disabled={!noteText.trim() || !noteFile.trim()}>
                        Add
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                <div className="space-y-2">
                  {annotations.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No notes yet.</p>
                  ) : (
                    annotations.map((a) => (
                      <div key={a.id} className="flex items-start justify-between bg-muted rounded-lg px-3 py-2">
                        <div>
                          <p className="text-xs font-medium text-muted-foreground">
                            {a.source_file} · p.{a.page} · {a.author_name}
                          </p>
                          <p className="text-sm">{a.note}</p>
                        </div>
                        <Button size="icon" variant="ghost" onClick={() => removeAnnotation(a.id)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    );
  }

  // Room list view
  return (
    <div className="h-full min-h-0 overflow-auto p-6 space-y-6">
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
        <div className="flex items-center justify-center text-center text-muted-foreground py-24">
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
