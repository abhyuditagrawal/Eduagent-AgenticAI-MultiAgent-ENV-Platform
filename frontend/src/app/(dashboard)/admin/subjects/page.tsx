"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Plus, BookOpen, Upload, Network, Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "sonner";

interface SubjectData {
  id: string;
  name: string;
  code: string;
  description: string | null;
}

export default function AdminSubjectsPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [subjects, setSubjects] = useState<SubjectData[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (session?.accessToken) loadSubjects();
  }, [session?.accessToken]);

  const loadSubjects = async () => {
    try {
      const res = await api.get("/api/subjects");
      setSubjects(res.data);
    } catch {
      toast.error("Failed to load subjects");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newCode.trim() || !newName.trim()) return;
    setCreating(true);
    try {
      await api.post("/api/subjects", {
        code: newCode.trim(),
        name: newName.trim(),
        description: newDesc.trim() || null,
      });
      toast.success("Subject created");
      setDialogOpen(false);
      setNewCode("");
      setNewName("");
      setNewDesc("");
      loadSubjects();
    } catch {
      toast.error("Failed to create subject");
    } finally {
      setCreating(false);
    }
  };

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
        <h1 className="text-2xl font-semibold">Manage Subjects</h1>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger render={<Button />}>
            <Plus className="h-4 w-4 mr-2" />
            Add Subject
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Subject</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 pt-2">
              <Input
                placeholder="Subject code (e.g. ML)"
                value={newCode}
                onChange={(e) => setNewCode(e.target.value)}
              />
              <Input
                placeholder="Subject name (e.g. Machine Learning)"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <Input
                placeholder="Description (optional)"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
              />
              <Button
                className="w-full"
                onClick={handleCreate}
                disabled={creating || !newCode.trim() || !newName.trim()}
              >
                {creating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Create Subject
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {subjects.map((subject) => (
          <Card key={subject.id}>
            <CardContent className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold">{subject.name}</h3>
                  <p className="text-sm text-muted-foreground">{subject.code}</p>
                  {subject.description && (
                    <p className="text-xs text-muted-foreground mt-1">{subject.description}</p>
                  )}
                </div>
              </div>
              <div className="flex gap-2 mt-3">
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={() => router.push(`/admin/concepts/${subject.id}`)}
                >
                  <BookOpen className="h-3.5 w-3.5 mr-1" />
                  Concepts
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={() => router.push("/admin/upload")}
                >
                  <Upload className="h-3.5 w-3.5 mr-1" />
                  Upload
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={() => router.push("/concept-map")}
                >
                  <Network className="h-3.5 w-3.5 mr-1" />
                  Graph
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
