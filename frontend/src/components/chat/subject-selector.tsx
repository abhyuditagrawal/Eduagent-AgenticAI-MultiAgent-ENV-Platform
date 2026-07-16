"use client";

import { useEffect, useState } from "react";
import { BookOpen } from "lucide-react";
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

  useEffect(() => {
    loadSubjects();
  }, []);

  const loadSubjects = async () => {
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
  };

  if (subjects.length === 0) return null;

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b bg-muted/30">
      <BookOpen className="h-4 w-4 text-muted-foreground" />
      <select
        value={value || ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="text-sm bg-transparent border-none outline-none cursor-pointer text-foreground"
      >
        <option value="">All subjects</option>
        {subjects.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name} ({s.code})
          </option>
        ))}
      </select>
    </div>
  );
}
