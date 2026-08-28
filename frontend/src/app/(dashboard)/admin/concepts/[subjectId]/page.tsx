"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useParams } from "next/navigation";
import { Plus, Loader2, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "sonner";

interface ConceptData {
  id: string;
  name: string;
  chapter: string | null;
  difficulty_tier: number;
}

export default function AdminConceptsPage() {
  const { data: session } = useSession();
  const params = useParams();
  const subjectId = params.subjectId as string;
  const [concepts, setConcepts] = useState<ConceptData[]>([]);
  const [loading, setLoading] = useState(true);
  const [syllabusText, setSyllabusText] = useState("");
  const [populating, setPopulating] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [syllabusDialogOpen, setSyllabusDialogOpen] = useState(false);
  const [newConceptName, setNewConceptName] = useState("");
  const [newConceptChapter, setNewConceptChapter] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (session?.accessToken && subjectId) loadConcepts();
  }, [session?.accessToken, subjectId]);

  const loadConcepts = async () => {
    try {
      const res = await api.get(`/api/concepts/${subjectId}`);
      setConcepts(res.data);
    } catch {
      toast.error("Failed to load concepts");
    } finally {
      setLoading(false);
    }
  };

  const handlePopulate = async () => {
    if (!syllabusText.trim()) return;
    setPopulating(true);
    try {
      const res = await api.post(`/api/concepts/${subjectId}/populate`, {
        syllabus_text: syllabusText.trim(),
      });
      toast.success(res.data.message);
      setSyllabusDialogOpen(false);
      setSyllabusText("");
      loadConcepts();
    } catch {
      toast.error("Failed to extract concepts");
    } finally {
      setPopulating(false);
    }
  };

  const handleAddConcept = async () => {
    if (!newConceptName.trim()) return;
    setAdding(true);
    try {
      await api.post(`/api/concepts/${subjectId}`, {
        name: newConceptName.trim(),
        chapter: newConceptChapter.trim() || null,
      });
      toast.success(`Added ${newConceptName.trim()}`);
      setAddDialogOpen(false);
      setNewConceptName("");
      setNewConceptChapter("");
      loadConcepts();
    } catch (err: unknown) {
      const detail =
        typeof err === "object" && err !== null && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data
              ?.detail
          : undefined;
      toast.error(detail || "Failed to add concept");
    } finally {
      setAdding(false);
    }
  };

  // Group by chapter
  const grouped: Record<string, ConceptData[]> = {};
  for (const c of concepts) {
    const ch = c.chapter || "Uncategorized";
    grouped[ch] = grouped[ch] || [];
    grouped[ch].push(c);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Concepts</h1>
          <p className="text-sm text-muted-foreground">{concepts.length} concepts</p>
        </div>
        <div className="flex gap-2">
          <Dialog open={syllabusDialogOpen} onOpenChange={setSyllabusDialogOpen}>
            <DialogTrigger render={<Button variant="outline" />}>
              <Sparkles className="h-4 w-4 mr-2" />
              Populate from Syllabus
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Extract Concepts from Syllabus</DialogTitle>
              </DialogHeader>
              <div className="space-y-3 pt-2">
                <textarea
                  className="w-full min-h-[200px] p-3 rounded-md border bg-background text-sm resize-y focus:outline-none focus:ring-2 focus:ring-primary/30"
                  placeholder="Paste your syllabus text here..."
                  value={syllabusText}
                  onChange={(e) => setSyllabusText(e.target.value)}
                />
                <Button
                  className="w-full"
                  onClick={handlePopulate}
                  disabled={populating || !syllabusText.trim()}
                >
                  {populating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Extract Concepts
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {Object.keys(grouped).length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p>No concepts yet. Use &quot;Populate from Syllabus&quot; to extract concepts automatically.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {Object.entries(grouped).map(([chapter, items]) => (
            <Card key={chapter}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">{chapter}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  {items.map((c) => (
                    <div
                      key={c.id}
                      className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-muted/50"
                    >
                      <span className="text-sm">{c.name}</span>
                      <Badge variant="outline" className="text-xs">
                        Tier {c.difficulty_tier}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
