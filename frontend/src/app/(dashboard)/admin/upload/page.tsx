"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Upload, FileText, CheckCircle2, XCircle, Clock, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api";
import { toast } from "sonner";

interface Subject {
  id: string;
  code: string;
  name: string;
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

export default function UploadPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [selectedSubject, setSelectedSubject] = useState("");
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    if (session?.user?.role !== "admin") {
      router.push("/chat");
      return;
    }
    loadSubjects();
    loadJobs();
  }, [session, router]);

  const loadSubjects = async () => {
    try {
      const res = await api.get("/api/subjects");
      setSubjects(res.data);
      if (res.data.length > 0) setSelectedSubject(res.data[0].id);
    } catch {
      toast.error("Failed to load subjects");
    }
  };

  const loadJobs = async () => {
    try {
      const res = await api.get("/api/ingest/jobs");
      setJobs(res.data);
    } catch {
      // Silently fail
    }
  };

  const uploadFile = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Only PDF files are accepted");
      return;
    }

    if (!selectedSubject) {
      toast.error("Please select a subject first");
      return;
    }

    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("subject_id", selectedSubject);

    try {
      await api.post("/api/ingest/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`Uploaded ${file.name} — processing started`);
      loadJobs();
    } catch {
      toast.error("Upload failed");
    } finally {
      setIsUploading(false);
    }
  }, [selectedSubject]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
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

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Upload Course Material</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Upload PDF</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Subject</label>
            <select
              value={selectedSubject}
              onChange={(e) => setSelectedSubject(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.code})
                </option>
              ))}
            </select>
          </div>

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
            onDrop={handleDrop}
          >
            <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground mb-2">
              Drag & drop a PDF file here, or
            </p>
            <Button
              variant="outline"
              disabled={isUploading}
              onClick={() =>
                document.getElementById("file-upload")?.click()
              }
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
              onChange={handleFileInput}
              className="hidden"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Ingestion History</CardTitle>
        </CardHeader>
        <CardContent>
          {jobs.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No uploads yet
            </p>
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className="flex items-center justify-between p-3 rounded-md border"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">{job.filename}</p>
                      <p className="text-xs text-muted-foreground">
                        {job.chunks > 0 && `${job.chunks} chunks · `}
                        {new Date(job.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  {statusBadge(job.status)}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
