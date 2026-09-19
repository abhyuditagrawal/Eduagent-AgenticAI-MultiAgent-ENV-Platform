"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Loader2, RotateCcw, Plus, Brain, CheckCircle, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import api from "@/lib/api";

interface Flashcard {
  id: string;
  front: string;
  back: string;
  source: string;
  easiness_factor: number;
  interval_days: number;
  repetitions: number;
  next_review_at: string | null;
}

interface FlashcardStats {
  total: number;
  due_now: number;
  mastered: number;
}

export default function FlashcardsPage() {
  const { data: session } = useSession();
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [stats, setStats] = useState<FlashcardStats>({ total: 0, due_now: 0, mastered: 0 });
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [mode, setMode] = useState<"browse" | "review" | "create">("browse");
  const [dueOnly, setDueOnly] = useState(false);
  const [newFront, setNewFront] = useState("");
  const [newBack, setNewBack] = useState("");

  useEffect(() => {
    if (session?.accessToken) {
      loadCards();
      loadStats();
    }
  }, [session?.accessToken, dueOnly]);

  const loadCards = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/flashcards?due_only=${dueOnly}`);
      setCards(res.data);
      setCurrentIndex(0);
      setFlipped(false);
    } catch {}
    setLoading(false);
  };

  const loadStats = async () => {
    try {
      const res = await api.get("/api/flashcards/stats");
      setStats(res.data);
    } catch {}
  };

  const handleReview = async (quality: number) => {
    if (!cards[currentIndex]) return;
    try {
      await api.post(`/api/flashcards/${cards[currentIndex].id}/review`, { quality });
      setFlipped(false);
      if (currentIndex < cards.length - 1) {
        setCurrentIndex(currentIndex + 1);
      } else {
        await loadCards();
        await loadStats();
      }
    } catch {}
  };

  const handleCreate = async () => {
    if (!newFront.trim() || !newBack.trim()) return;
    try {
      await api.post("/api/flashcards", { front: newFront, back: newBack });
      setNewFront("");
      setNewBack("");
      await loadCards();
      await loadStats();
    } catch {}
  };

  const current = cards[currentIndex];

  return (
    <div className="h-full min-h-0 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Flashcards</h1>
        <div className="flex gap-2">
          <Button
            variant={mode === "browse" ? "default" : "outline"}
            size="sm"
            onClick={() => setMode("browse")}
          >
            <Brain className="h-4 w-4 mr-1" /> Browse
          </Button>
          <Button
            variant={mode === "review" ? "default" : "outline"}
            size="sm"
            onClick={() => { setMode("review"); setDueOnly(true); }}
          >
            <Clock className="h-4 w-4 mr-1" /> Review Due ({stats.due_now})
          </Button>
          <Button
            variant={mode === "create" ? "default" : "outline"}
            size="sm"
            onClick={() => setMode("create")}
          >
            <Plus className="h-4 w-4 mr-1" /> Create
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-2xl font-bold">{stats.total}</p>
            <p className="text-xs text-muted-foreground">Total Cards</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-2xl font-bold text-orange-500">{stats.due_now}</p>
            <p className="text-xs text-muted-foreground">Due Now</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-2xl font-bold text-green-500">{stats.mastered}</p>
            <p className="text-xs text-muted-foreground">Mastered</p>
          </CardContent>
        </Card>
      </div>

      {mode === "create" ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Create Flashcard</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium">Front (Question)</label>
              <Textarea
                value={newFront}
                onChange={(e) => setNewFront(e.target.value)}
                placeholder="What is the question?"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Back (Answer)</label>
              <Textarea
                value={newBack}
                onChange={(e) => setNewBack(e.target.value)}
                placeholder="What is the answer?"
                className="mt-1"
              />
            </div>
            <Button onClick={handleCreate} disabled={!newFront.trim() || !newBack.trim()}>
              Create Flashcard
            </Button>
          </CardContent>
        </Card>
      ) : loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : cards.length === 0 ? (
        <div className="flex items-center justify-center text-center text-muted-foreground py-24">
          <div>
            <Brain className="h-12 w-12 mx-auto mb-4 opacity-30" />
            <p className="text-lg font-medium">No flashcards yet</p>
            <p className="text-sm">Flashcards are auto-generated from your conversations, or create your own.</p>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center">
          {/* Flashcard */}
          <div
            className="w-full max-w-lg cursor-pointer"
            onClick={() => setFlipped(!flipped)}
          >
            <Card className="min-h-[250px] flex items-center justify-center transition-all duration-300 hover:shadow-lg">
              <CardContent className="text-center p-8">
                <p className="text-xs text-muted-foreground mb-4">
                  {flipped ? "ANSWER" : "QUESTION"} — {currentIndex + 1}/{cards.length}
                </p>
                <p className="text-lg leading-relaxed">
                  {flipped ? current?.back : current?.front}
                </p>
                {!flipped && (
                  <p className="text-xs text-muted-foreground mt-6">Click to reveal answer</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Review buttons (only show after flip) */}
          {flipped && mode === "review" && (
            <div className="flex gap-2 mt-6">
              <Button variant="destructive" size="sm" onClick={() => handleReview(1)}>
                Forgot
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleReview(3)}>
                Hard
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleReview(4)}>
                Good
              </Button>
              <Button variant="default" size="sm" onClick={() => handleReview(5)}>
                Easy
              </Button>
            </div>
          )}

          {/* Navigation */}
          <div className="flex gap-2 mt-4">
            <Button
              variant="ghost"
              size="sm"
              disabled={currentIndex === 0}
              onClick={() => { setCurrentIndex(currentIndex - 1); setFlipped(false); }}
            >
              Previous
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={currentIndex >= cards.length - 1}
              onClick={() => { setCurrentIndex(currentIndex + 1); setFlipped(false); }}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
