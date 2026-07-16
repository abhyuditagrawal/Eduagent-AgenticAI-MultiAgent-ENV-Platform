"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { BookOpen, GraduationCap, Mic } from "lucide-react";

interface ConceptData {
  id: string;
  name: string;
  confidence: number;
  attempts: number;
  last_seen: string | null;
  next_review: string | null;
  status: string;
}

interface ChapterData {
  name: string;
  average_confidence: number;
  concepts: ConceptData[];
}

interface MasteryHeatmapProps {
  chapters: ChapterData[];
}

const STATUS_COLORS: Record<string, string> = {
  mastered: "bg-green-500/80 hover:bg-green-500 text-white",
  proficient: "bg-blue-500/80 hover:bg-blue-500 text-white",
  developing: "bg-orange-400/80 hover:bg-orange-400 text-white",
  not_started: "bg-gray-300 hover:bg-gray-400 text-gray-700 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-300",
};

export function MasteryHeatmap({ chapters }: MasteryHeatmapProps) {
  const router = useRouter();

  const navigateToChat = (conceptName: string, agent: string) => {
    const overrideMap: Record<string, string> = {
      qa: "conceptual_doubt",
      protege: "teach_me",
      viva: "viva",
    };
    const override = overrideMap[agent] || "conceptual_doubt";
    router.push(`/chat?override=${override}&concept=${encodeURIComponent(conceptName)}`);
  };

  return (
    <div className="space-y-4">
      {chapters.map((chapter) => (
        <div key={chapter.name}>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-muted-foreground">{chapter.name}</h4>
            <span className="text-xs text-muted-foreground">
              Avg: {Math.round(chapter.average_confidence * 100)}%
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {chapter.concepts.map((concept) => (
              <Popover key={concept.id}>
                <PopoverTrigger>
                  <div
                    className={`px-2.5 py-1.5 rounded text-xs font-medium cursor-pointer transition-colors ${STATUS_COLORS[concept.status] || STATUS_COLORS.not_started}`}
                    title={`${concept.name}: ${Math.round(concept.confidence * 100)}%`}
                  >
                    {concept.name.length > 20 ? concept.name.slice(0, 18) + "..." : concept.name}
                    <span className="ml-1 opacity-75">{Math.round(concept.confidence * 100)}%</span>
                  </div>
                </PopoverTrigger>
                <PopoverContent className="w-64 p-3" align="start">
                  <div className="space-y-2">
                    <div>
                      <p className="font-medium text-sm">{concept.name}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Confidence: {Math.round(concept.confidence * 100)}% · {concept.attempts} attempts
                      </p>
                      {concept.last_seen && (
                        <p className="text-xs text-muted-foreground">
                          Last seen: {new Date(concept.last_seen).toLocaleDateString()}
                        </p>
                      )}
                      {concept.next_review && (
                        <p className="text-xs text-muted-foreground">
                          Next review: {new Date(concept.next_review).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-1.5">
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs flex-1"
                        onClick={() => navigateToChat(concept.name, "qa")}
                      >
                        <BookOpen className="h-3 w-3 mr-1" />
                        Review
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs flex-1"
                        onClick={() => navigateToChat(concept.name, "protege")}
                      >
                        <GraduationCap className="h-3 w-3 mr-1" />
                        Teach
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs flex-1"
                        onClick={() => navigateToChat(concept.name, "viva")}
                      >
                        <Mic className="h-3 w-3 mr-1" />
                        Quiz
                      </Button>
                    </div>
                  </div>
                </PopoverContent>
              </Popover>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
