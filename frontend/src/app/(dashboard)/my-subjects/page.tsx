"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Upload,
  FileText,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Network,
  MessageSquare,
  BookOpen,
  Trash2,
  LogOut,
  X,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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

interface SubjectData {
  id: string;
  name: string;
  code: string;
  description: string | null;
}

interface ConceptData {
  id: string;
  name: string;
  chapter: string | null;
  difficulty_tier: number;
}

interface IngestionJob {
  id: string;
  subject_id: string;
  filename: string;
  status: string;
  chunks: number;
  error: string | null;
  created_at: string;
}

const POLL_INTERVAL_MS = 3000;

export default function MySubjectsPage() {
  const { data: session } = useSession();
  const router = useRouter();

  const [subjects, setSubjects] = useState<SubjectData[]>([]);
  const [activeSubject, setActiveSubject] = useState<SubjectData | null>(null);
  const [concepts, setConcepts] = useState<ConceptData[]>([]);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [loading, setLoading] = useState(true);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  const [isUploading, setIsUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const [syllabus, setSyllabus] = useState("");
  const [generating, setGenerating] = useState(false);

  const [subjectToRemove, setSubjectToRemove] = useState<SubjectData | null>(null);
  const [removing, setRemoving] = useState(false);
  const [deletingConceptId, setDeletingConceptId] = useState<string | null>(null);

  const loadSubjects = useCallback(async () => {
    try {
      const res = await api.get("/api/subjects/enrolled");
      setSubjects(res.data);
      setActiveSubject((current) => current ?? res.data[0] ?? null);
    } catch {
      toast.error("Failed to load your subjects");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSubjectDetail = useCallback(async (subjectId: string) => {
    try {
      const [conceptRes, jobRes] = await Promise.all([
        api.get(`/api/concepts/${subjectId}`),
        api.get("/api/ingest/jobs"),
      ]);
      setConcepts(conceptRes.data);
      setJobs(
        jobRes.data.filter((j: IngestionJob) => j.subject_id === subjectId)
      );
    } catch {
      // Detail panels degrade to empty rather than blocking the page
    }
  }, []);

  useEffect(() => {
    if (session?.accessToken) loadSubjects();
  }, [session?.accessToken, loadSubjects]);

  useEffect(() => {
    if (activeSubject) loadSubjectDetail(activeSubject.id);
  }, [activeSubject, loadSubjectDetail]);

  // While a PDF is being processed, keep refreshing so concepts appear as soon
  // as ingestion finishes building them.
  const hasRunningJob = jobs.some(
    (j) => j.status === "pending" || j.status === "processing"
  );
  useEffect(() => {
    if (!hasRunningJob || !activeSubject) return;
    const timer = setInterval(
      () => loadSubjectDetail(activeSubject.id),
      POLL_INTERVAL_MS
    );
    return () => clearInterval(timer);
  }, [hasRunningJob, activeSubject, loadSubjectDetail]);

  const handleCreate = async () => {
    if (!newCode.trim() || !newName.trim()) return;
    setCreating(true);
    try {
      const res = await api.post("/api/subjects", {
        code: newCode.trim(),
        name: newName.trim(),
        description: newDesc.trim() || null,
      });
      toast.success(`Created ${res.data.name} — upload your notes to get started`);
      setDialogOpen(false);
      setNewCode("");
      setNewName("");
      setNewDesc("");
      await loadSubjects();
      setActiveSubject(res.data);
    } catch (err: unknown) {
      const detail =
        typeof err === "object" && err !== null && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data
              ?.detail
          : undefined;
      toast.error(detail || "Failed to create subject");
    } finally {
      setCreating(false);
    }
  };

  /** Read FastAPI's `detail` off an axios error so the real reason is shown. */
  const errorDetail = (err: unknown, fallback: string): string => {
    const detail =
      typeof err === "object" && err !== null && "response" in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data
            ?.detail
        : undefined;
    return detail || fallback;
  };

  /** Drop the removed subject from local state and pick a sensible replacement. */
  const afterSubjectRemoved = (removedId: string) => {
    const remaining = subjects.filter((s) => s.id !== removedId);
    setSubjects(remaining);
    setActiveSubject((current) =>
      current?.id === removedId ? remaining[0] ?? null : current
    );
    setSubjectToRemove(null);
  };

  const handleLeaveSubject = async (subject: SubjectData) => {
    setRemoving(true);
    try {
      await api.delete(`/api/subjects/${subject.id}/enroll`);
      toast.success(`Left ${subject.name} — it stays available to others`);
      afterSubjectRemoved(subject.id);
    } catch (err: unknown) {
      toast.error(errorDetail(err, "Could not leave that subject"));
    } finally {
      setRemoving(false);
    }
  };

  const handleDeleteSubject = async (subject: SubjectData) => {
    setRemoving(true);
    try {
      await api.delete(`/api/subjects/${subject.id}`);
      toast.success(`Deleted ${subject.name} and its material`);
      afterSubjectRemoved(subject.id);
    } catch (err: unknown) {
      // The API refuses when other students are enrolled, and says so.
      toast.error(errorDetail(err, "Could not delete that subject"));
    } finally {
      setRemoving(false);
    }
  };

  const handleDeleteConcept = async (concept: ConceptData) => {
    if (!activeSubject) return;
    setDeletingConceptId(concept.id);
    try {
      await api.delete(`/api/concepts/${activeSubject.id}/${concept.id}`);
      setConcepts((prev) => prev.filter((c) => c.id !== concept.id));
      toast.success(`Removed ${concept.name}`);
    } catch (err: unknown) {
      toast.error(errorDetail(err, "Could not remove that concept"));
    } finally {
      setDeletingConceptId(null);
    }
  };

  const uploadFile = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        toast.error("Only PDF files are accepted");
        return;
      }
      if (!activeSubject) {
        toast.error("Create or select a subject first");
        return;
      }

      setIsUploading(true);
      const formData = new FormData();
      formData.append("file", file);
      formData.append("subject_id", activeSubject.id);

      try {
        await api.post("/api/ingest/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        toast.success(
          `Uploaded ${file.name} — extracting text and building your concept map`
        );
        loadSubjectDetail(activeSubject.id);
      } catch {
        toast.error("Upload failed");
      } finally {
        setIsUploading(false);
      }
    },
    [activeSubject, loadSubjectDetail]
  );

  const handleGenerateFromSyllabus = async () => {
    if (!activeSubject || !syllabus.trim()) return;
    setGenerating(true);
    try {
      const res = await api.post(`/api/concepts/${activeSubject.id}/populate`, {
        syllabus_text: syllabus.trim(),
      });
      toast.success(`Added ${res.data.count} concepts`);
      setSyllabus("");
      loadSubjectDetail(activeSubject.id);
    } catch {
      toast.error("Could not extract concepts from that text");
    } finally {
      setGenerating(false);
    }
  };

  const statusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
            <CheckCircle2 className="h-3 w-3 mr-1" />
            Completed
          </Badge>
        );
      case "failed":
        return (
          <Badge variant="destructive">
            <XCircle className="h-3 w-3 mr-1" />
            Failed
          </Badge>
        );
      case "processing":
        return (
          <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">
            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            Processing
          </Badge>
        );
      default:
        return (
          <Badge variant="secondary">
            <Clock className="h-3 w-3 mr-1" />
            Pending
          </Badge>
        );
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const createDialog = (
    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
      <DialogTrigger render={<Button />}>
        <Plus className="h-4 w-4 mr-2" />
        New Subject
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a subject you&apos;re studying</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 pt-2">
          <Input
            placeholder="Short code (e.g. DBMS)"
            value={newCode}
            onChange={(e) => setNewCode(e.target.value)}
          />
          <Input
            placeholder="Subject name (e.g. Database Management Systems)"
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
  );

  // Leaving and deleting differ in blast radius, so the choice is made here
  // rather than guessed for the student.
  const removeDialog = (
    <Dialog
      open={subjectToRemove !== null}
      onOpenChange={(open) => {
        if (!open && !removing) setSubjectToRemove(null);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Remove {subjectToRemove?.name}?</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1">
            <p className="text-sm font-medium">Leave the subject</p>
            <p className="text-sm text-muted-foreground">
              Removes it from your list and discards your progress on it. The
              subject, its concepts and its uploaded material stay for everyone
              else.
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium text-destructive">
              Delete permanently
            </p>
            <p className="text-sm text-muted-foreground">
              Deletes the subject, its concepts and its uploaded material for
              everyone. Your past chats are kept, but no longer linked to it.
              Only possible if nobody else is enrolled.
            </p>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="ghost"
              disabled={removing}
              onClick={() => setSubjectToRemove(null)}
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              disabled={removing}
              onClick={() =>
                subjectToRemove && handleLeaveSubject(subjectToRemove)
              }
            >
              {removing ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <LogOut className="h-4 w-4 mr-2" />
              )}
              Leave subject
            </Button>
            <Button
              variant="destructive"
              disabled={removing}
              onClick={() =>
                subjectToRemove && handleDeleteSubject(subjectToRemove)
              }
            >
              {removing ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4 mr-2" />
              )}
              Delete permanently
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );

  if (subjects.length === 0) {
    return (
      <div className="flex items-center justify-center h-full p-6">
        <div className="max-w-md text-center space-y-4">
          <BookOpen className="h-12 w-12 mx-auto text-primary" />
          <h2 className="text-2xl font-semibold">Start with your first subject</h2>
          <p className="text-muted-foreground">
            Add a subject you&apos;re studying, then upload your own notes or
            textbook PDFs. EduAgent reads them, builds your concept map, and every
            agent answers from your material.
          </p>
          <div className="flex justify-center">{createDialog}</div>
          {removeDialog}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6"><div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">My Subjects</h1>
          <p className="text-sm text-muted-foreground">
            Upload your own material — everything the agents know comes from it.
          </p>
        </div>
        {createDialog}
      </div>

      <div className="flex flex-wrap gap-2">
        {subjects.map((subject) => (
          <Button
            key={subject.id}
            variant={activeSubject?.id === subject.id ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveSubject(subject)}
          >
            {subject.name}
            <span className="ml-2 opacity-60 text-xs">{subject.code}</span>
          </Button>
        ))}
      </div>

      {activeSubject && (
        <>
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle className="text-lg">
                Upload material for {activeSubject.name}
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-destructive"
                onClick={() => setSubjectToRemove(activeSubject)}
                title={`Remove ${activeSubject.name}`}
              >
                <Trash2 className="h-3.5 w-3.5 mr-1" />
                Remove subject
              </Button>
            </CardHeader>
            <CardContent>
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  dragOver
                    ? "border-primary bg-primary/5"
                    : "border-muted-foreground/25 hover:border-muted-foreground/50"
                }`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const file = e.dataTransfer.files?.[0];
                  if (file) uploadFile(file);
                }}
              >
                <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                <p className="text-sm text-muted-foreground mb-2">
                  Drag &amp; drop your lecture notes or textbook PDF, or
                </p>
                <Button
                  variant="outline"
                  disabled={isUploading}
                  onClick={() => document.getElementById("file-upload")?.click()}
                >
                  {isUploading ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <FileText className="h-4 w-4 mr-2" />
                  )}
                  Browse Files
                </Button>
                <input
                  id="file-upload"
                  type="file"
                  accept=".pdf"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) uploadFile(file);
                  }}
                  className="hidden"
                />
              </div>

              {jobs.length > 0 && (
                <div className="space-y-3 mt-4">
                  {jobs.map((job) => (
                    <div
                      key={job.id}
                      className="flex items-center justify-between p-3 rounded-md border"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <FileText className="h-5 w-5 text-muted-foreground shrink-0" />
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">
                            {job.filename}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {job.chunks > 0 && `${job.chunks} chunks · `}
                            {new Date(job.created_at).toLocaleString()}
                          </p>
                          {job.error && (
                            <p className="text-xs text-destructive">{job.error}</p>
                          )}
                        </div>
                      </div>
                      {statusBadge(job.status)}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                Concepts found in your material ({concepts.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {concepts.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {hasRunningJob
                    ? "Reading your upload and extracting concepts…"
                    : "No concepts yet. Upload a PDF above, or paste your syllabus below."}
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {concepts.map((concept) => (
                    <Badge
                      key={concept.id}
                      variant="secondary"
                      className="group/concept gap-1 pr-1"
                    >
                      {concept.name}
                      {concept.chapter && (
                        <span className="ml-1 opacity-60">
                          · {concept.chapter}
                        </span>
                      )}
                      <button
                        type="button"
                        aria-label={`Remove ${concept.name}`}
                        title={`Remove ${concept.name}`}
                        disabled={deletingConceptId === concept.id}
                        onClick={() => handleDeleteConcept(concept)}
                        className="ml-0.5 rounded-sm p-0.5 opacity-50 transition-opacity hover:bg-destructive/15 hover:text-destructive hover:opacity-100 focus-visible:opacity-100 disabled:opacity-30"
                      >
                        {deletingConceptId === concept.id ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <X className="h-3 w-3" />
                        )}
                      </button>
                    </Badge>
                  ))}
                </div>
              )}

              <div className="space-y-2 pt-2">
                <label className="text-sm font-medium">
                  Or paste your syllabus / unit list
                </label>
                <Textarea
                  rows={4}
                  placeholder="Unit 1: Normalisation, ER Modelling…"
                  value={syllabus}
                  onChange={(e) => setSyllabus(e.target.value)}
                />
                <Button
                  variant="outline"
                  onClick={handleGenerateFromSyllabus}
                  disabled={generating || !syllabus.trim()}
                >
                  {generating ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : null}
                  Extract Concepts
                </Button>
              </div>

              {concepts.length > 0 && (
                <div className="flex gap-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => router.push("/concept-map")}
                  >
                    <Network className="h-3.5 w-3.5 mr-1" />
                    View Concept Map
                  </Button>
                  <Button size="sm" onClick={() => router.push("/chat")}>
                    <MessageSquare className="h-3.5 w-3.5 mr-1" />
                    Ask the Agents
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
      {removeDialog}
    </div>
    </div>
  );
}
