"use client";

import { useState, useRef } from "react";
import { FileText, Upload, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface CritiqueUploadProps {
  onSubmit: (text: string) => void;
  disabled?: boolean;
}

export function CritiqueUpload({ onSubmit, disabled }: CritiqueUploadProps) {
  const [text, setText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  const charCount = text.length;

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type === "text/plain" || file.name.endsWith(".md") || file.name.endsWith(".txt")) {
      const content = await file.text();
      setText(content);
    }
  };

  const handleSubmit = () => {
    if (text.trim()) {
      onSubmit(text.trim());
      setText("");
    }
  };

  return (
    <div className="border-t bg-card">
      <div className="px-4 py-2 border-b bg-yellow-50/50 dark:bg-yellow-950/20 flex items-center gap-2">
        <FileText className="h-4 w-4 text-yellow-600" />
        <span className="text-sm font-medium text-yellow-700 dark:text-yellow-400">
          Essay / Assignment Critique Mode
        </span>
        <span className="text-xs text-muted-foreground ml-auto">
          Paste your essay or upload a .txt/.md file
        </span>
      </div>

      <div className="p-4 space-y-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste your essay or assignment text here for critique..."
          className="w-full min-h-[200px] max-h-[400px] p-3 rounded-md border bg-background text-sm resize-y focus:outline-none focus:ring-2 focus:ring-primary/30"
          disabled={disabled}
        />

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md"
              className="hidden"
              onChange={handleFileUpload}
            />
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled}
            >
              <Upload className="h-3.5 w-3.5 mr-1" />
              Upload .txt/.md
            </Button>

            <div className="flex gap-2">
              <Badge variant="secondary" className="text-xs">
                {wordCount} words
              </Badge>
              <Badge variant="secondary" className="text-xs">
                {charCount} chars
              </Badge>
            </div>
          </div>

          <Button
            size="sm"
            className="h-8"
            onClick={handleSubmit}
            disabled={disabled || text.trim().length < 50}
          >
            <Send className="h-3.5 w-3.5 mr-1" />
            Submit for Review
          </Button>
        </div>
      </div>
    </div>
  );
}
