"use client";

import { useState, useRef } from "react";
import { ImagePlus, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import api from "@/lib/api";

interface ImageUploadProps {
  onAnalysis: (analysis: string) => void;
}

export function ImageUpload({ onAnalysis }: ImageUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;

    if (!["image/jpeg", "image/png", "image/gif", "image/webp"].includes(f.type)) {
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      return;
    }

    setFile(f);
    const reader = new FileReader();
    reader.onload = (ev) => setPreview(ev.target?.result as string);
    reader.readAsDataURL(f);
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setAnalyzing(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("question", question || "Explain this diagram or image in detail.");

    try {
      const res = await api.post("/api/image-chat", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onAnalysis(res.data.analysis);
      handleClose();
    } catch {
      onAnalysis("Failed to analyze image. Please try again.");
    }
    setAnalyzing(false);
  };

  const handleClose = () => {
    setFile(null);
    setPreview(null);
    setQuestion("");
    setOpen(false);
  };

  if (!open) {
    return (
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        onClick={() => setOpen(true)}
        title="Upload image/diagram"
      >
        <ImagePlus className="h-4 w-4" />
      </Button>
    );
  }

  return (
    <Card className="absolute bottom-full mb-2 left-0 right-0 z-20">
      <CardContent className="pt-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Upload Image/Diagram</span>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {preview ? (
          <div className="relative">
            <img
              src={preview}
              alt="Preview"
              className="w-full max-h-48 object-contain rounded border"
            />
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-1 right-1 h-6 w-6 bg-background/80"
              onClick={() => { setFile(null); setPreview(null); }}
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
        ) : (
          <div
            className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => inputRef.current?.click()}
          >
            <ImagePlus className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Click to upload (JPEG, PNG, GIF, WebP)</p>
            <p className="text-xs text-muted-foreground">Max 10MB</p>
          </div>
        )}

        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          onChange={handleFileSelect}
          className="hidden"
        />

        {file && (
          <>
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about this image (optional)"
            />
            <Button
              className="w-full"
              onClick={handleAnalyze}
              disabled={analyzing}
            >
              {analyzing ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1" />
              ) : (
                <ImagePlus className="h-4 w-4 mr-1" />
              )}
              Analyze Image
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
