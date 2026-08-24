"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, TriangleAlert } from "lucide-react";
import api from "@/lib/api";

interface Subject {
  id: string;
  code: string;
  name: string;
}

interface SubjectSelectorProps {
  value: string | null;
  onChange: (subjectId: string | null) => void;
}

export function SubjectSelector({ value, onChange }: SubjectSelectorProps) {
  const [subjects, setSubjects] = useState<Subject[]>([]);

  const loadSubjects = useCallback(async () => {
    try {
      const res = await api.get("/api/subjects/enrolled");
      setSubjects(res.data);
    } catch {
      // Try all subjects as fallback
      try {
        const res = await api.get("/api/subjects");
        setSubjects(res.data);
      } catch {
        // Silently fail
      }
    }
  }, []);

  useEffect(() => {
    loadSubjects();
  }, [loadSubjects]);

  // Retrieval is scoped to a subject: with none selected the agents never search
  // the uploaded course material at all. Default to the first enrolment so the
  // common case is grounded, rather than silently answering from general
  // knowledge and looking like the syllabus was never read.
  //
  // Only ever once — re-applying it would override a deliberate switch back to
  // "No subject".
  const autoSelected = useRef(false);
  useEffect(() => {
    if (autoSelected.current) return;
    if (!value && subjects.length > 0) {
      autoSelected.current = true;
      onChange(subjects[0].id);
    }
  }, [subjects, value, onChange]);

  if (subjects.length === 0) return null;

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b bg-muted/30">
      <BookOpen className="h-4 w-4 text-muted-foreground shrink-0" />
      <select
        value={value || ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="text-sm bg-transparent border-none outline-none cursor-pointer text-foreground"
      >
        <option value="">No subject (general chat)</option>
        {subjects.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name} ({s.code})
          </option>
        ))}
      </select>

      {!value && (
        <span
          className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-500"
          title="Pick a subject so the agents can search your uploaded course material."
        >
          <TriangleAlert className="h-3.5 w-3.5 shrink-0" />
          <span className="hidden sm:inline">Course material not searched</span>
        </span>
      )}
    </div>
  );
}
