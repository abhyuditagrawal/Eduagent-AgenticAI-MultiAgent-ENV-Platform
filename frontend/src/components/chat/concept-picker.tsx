"use client";

import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import api from "@/lib/api";

interface Concept {
  id: string;
  name: string;
  chapter: string | null;
  difficulty_tier: number;
}

interface ConceptPickerProps {
  subjectId: string | null;
  mode: "protege" | "viva";
  onSelect: (concepts: Concept[]) => void;
  onClose: () => void;
}

export function ConceptPicker({
  subjectId,
  mode,
  onSelect,
  onClose,
}: ConceptPickerProps) {
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (subjectId) loadConcepts();
  }, [subjectId]);

  const loadConcepts = async () => {
    try {
      setLoading(true);
      const res = await api.get(`/api/concepts/${subjectId}`);
      setConcepts(res.data);
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  };

  const toggle = (id: string) => {
    const next = new Set(selected);
    if (mode === "protege") {
      // Single select for protege
      next.clear();
      next.add(id);
    } else {
      // Multi-select for viva
      if (next.has(id)) next.delete(id);
      else next.add(id);
    }
    setSelected(next);
  };

  const filtered = concepts.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      (c.chapter || "").toLowerCase().includes(search.toLowerCase())
  );

  // Group by chapter
  const grouped: Record<string, Concept[]> = {};
  for (const c of filtered) {
    const ch = c.chapter || "Uncategorized";
    grouped[ch] = grouped[ch] || [];
    grouped[ch].push(c);
  }

  const handleConfirm = () => {
    const chosen = concepts.filter((c) => selected.has(c.id));
    onSelect(chosen);
  };

  const confidenceColor = (tier: number) => {
    if (tier >= 3) return "border-red-300 text-red-600 dark:border-red-700 dark:text-red-400";
    if (tier >= 2) return "border-yellow-300 text-yellow-600 dark:border-yellow-700 dark:text-yellow-400";
    return "border-green-300 text-green-600 dark:border-green-700 dark:text-green-400";
  };

  if (!subjectId) {
    return (
      <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
        <div className="bg-card rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
          <p className="text-center text-muted-foreground">
            Please select a subject first.
          </p>
          <Button className="mt-4 w-full" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
      <div className="bg-card rounded-lg max-w-lg w-full mx-4 shadow-xl flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between">
          <div>
            <h3 className="font-semibold">
              {mode === "protege"
                ? "Which concept do you want to teach?"
                : "Which topics should the viva cover?"}
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              {mode === "protege"
                ? "Select one concept to explain"
                : "Select multiple topics (or leave empty for auto)"}
            </p>
          </div>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Search */}
        <div className="p-3 border-b">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search concepts..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
        </div>

        {/* Concept list */}
        <ScrollArea className="flex-1 min-h-0">
          <div className="p-3 space-y-4">
            {loading ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                Loading concepts...
              </p>
            ) : Object.keys(grouped).length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No concepts found. Populate concepts first.
              </p>
            ) : (
              Object.entries(grouped).map(([chapter, items]) => (
                <div key={chapter}>
                  <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                    {chapter}
                  </h4>
                  <div className="space-y-1">
                    {items.map((c) => (
                      <button
                        key={c.id}
                        onClick={() => toggle(c.id)}
                        className={`w-full text-left px-3 py-2 rounded-md text-sm flex items-center justify-between transition-colors ${
                          selected.has(c.id)
                            ? "bg-primary/10 ring-1 ring-primary"
                            : "hover:bg-muted"
                        }`}
                      >
                        <span className="truncate">{c.name}</span>
                        <Badge
                          variant="outline"
                          className={`text-xs ml-2 shrink-0 ${confidenceColor(c.difficulty_tier)}`}
                        >
                          Tier {c.difficulty_tier}
                        </Badge>
                      </button>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>

        {/* Footer */}
        <div className="p-3 border-t flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {selected.size} selected
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleConfirm}
              disabled={mode === "protege" && selected.size === 0}
            >
              {mode === "protege" ? "Start Teaching" : "Start Viva"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
