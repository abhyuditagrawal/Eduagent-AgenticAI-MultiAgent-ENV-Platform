"use client";

import { useEffect, useState, useRef } from "react";
import { useSession } from "next-auth/react";
import { Loader2, Swords, Send, Scale, Shield, Zap } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { streamDebate, type SSEEvent } from "@/lib/sse";
import { toast } from "sonner";
import api from "@/lib/api";

interface SubjectInfo {
  id: string;
  name: string;
  code: string;
}

interface Turn {
  role: string;
  label: string;
  content: string;
}

const ROLE_STYLES: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
  proponent: { icon: Shield, color: "text-blue-600 dark:text-blue-400", bg: "border-blue-500 bg-blue-500/5" },
  skeptic: { icon: Zap, color: "text-amber-600 dark:text-amber-400", bg: "border-amber-500 bg-amber-500/5" },
  judge: { icon: Scale, color: "text-emerald-600 dark:text-emerald-400", bg: "border-emerald-500 bg-emerald-500/5" },
};

export default function DebatePage() {
  const { data: session } = useSession();
  const [subjects, setSubjects] = useState<SubjectInfo[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [thinking, setThinking] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (session?.accessToken) loadSubjects();
  }, [session?.accessToken]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, thinking]);

  const loadSubjects = async () => {
    try {
      const res = await api.get("/api/subjects/enrolled");
      setSubjects(res.data);
      if (res.data.length > 0) setSelectedSubject(res.data[0].id);
    } catch {}
  };

  const runDebate = async () => {
    if (!question.trim() || running) return;
    setTurns([]);
    setThinking(null);
    setRunning(true);

    try {
      await streamDebate(question, selectedSubject, 1, (event: SSEEvent) => {
        switch (event.type) {
          case "turn_start":
            setThinking((event.data.label as string) || "Thinking");
            break;
          case "turn":
            setThinking(null);
            setTurns((prev) => [
              ...prev,
              {
                role: event.data.role as string,
                label: event.data.label as string,
                content: event.data.content as string,
              },
            ]);
            break;
          case "done":
            setThinking(null);
            break;
          case "error":
            toast.error((event.data.message as string) || "Debate error");
            break;
        }
      });
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Debate failed");
    } finally {
      setRunning(false);
      setThinking(null);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="border-b px-6 pt-4 pb-3 flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Swords className="h-6 w-6" /> Debate Arena
          <span className="text-xs font-normal text-muted-foreground ml-2">
            Two agents argue • a judge decides
          </span>
        </h1>
        <Tabs value={selectedSubject || ""} onValueChange={setSelectedSubject}>
          <TabsList>
            {subjects.map((s) => (
              <TabsTrigger key={s.id} value={s.id}>
                {s.code}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-4">
        {turns.length === 0 && !running && (
          <div className="flex-1 flex items-center justify-center text-center text-muted-foreground py-20">
            <div>
              <Swords className="h-12 w-12 mx-auto mb-4 opacity-30" />
              <p className="text-lg font-medium">Pose a hard or ambiguous question</p>
              <p className="text-sm max-w-md">
                A Proponent argues the standard answer, a Skeptic challenges it, and a
                neutral Judge synthesises a balanced, evidence-grounded consensus.
              </p>
            </div>
          </div>
        )}

        {turns.map((turn, i) => {
          const style = ROLE_STYLES[turn.role] || ROLE_STYLES.judge;
          const Icon = style.icon;
          return (
            <Card key={i} className={`border-l-4 ${style.bg}`}>
              <CardContent className="pt-4">
                <div className={`flex items-center gap-2 font-semibold mb-2 ${style.color}`}>
                  <Icon className="h-4 w-4" />
                  {turn.label}
                </div>
                <p className="text-sm whitespace-pre-wrap leading-relaxed">
                  {turn.content}
                </p>
              </CardContent>
            </Card>
          );
        })}

        {thinking && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground pl-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            {thinking} is thinking…
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t p-4 flex gap-2">
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Is a stack always better than a queue for DFS?"
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && runDebate()}
          disabled={running}
        />
        <Button onClick={runDebate} disabled={running || !question.trim()}>
          {running ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
          <span className="ml-1">Debate</span>
        </Button>
      </div>
    </div>
  );
}
