"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  Loader2,
  Compass,
  CheckCircle2,
  Lock,
  Rocket,
  Star,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import api from "@/lib/api";

interface SubjectInfo {
  id: string;
  name: string;
  code: string;
}

interface ConceptItem {
  id: string;
  name: string;
  chapter: string | null;
  difficulty: number;
  mastery: number;
  readiness_score?: number;
  prereq_readiness?: number;
  missing_prerequisites?: { id: string; name: string; mastery: number }[];
}

interface FrontierData {
  mastered: ConceptItem[];
  frontier: ConceptItem[];
  locked: ConceptItem[];
  next_best: ConceptItem | null;
  counts: { mastered: number; frontier: number; locked: number; total: number };
}

export default function KnowledgeFrontierPage() {
  const { data: session } = useSession();
  const [subjects, setSubjects] = useState<SubjectInfo[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [data, setData] = useState<FrontierData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (session?.accessToken) loadSubjects();
  }, [session?.accessToken]);

  useEffect(() => {
    if (selectedSubject) loadFrontier(selectedSubject);
  }, [selectedSubject]);

  const loadSubjects = async () => {
    try {
      const res = await api.get("/api/subjects/enrolled");
      setSubjects(res.data);
      if (res.data.length > 0) setSelectedSubject(res.data[0].id);
      else setLoading(false);
    } catch {
      setLoading(false);
    }
  };

  const loadFrontier = async (subjectId: string) => {
    setLoading(true);
    try {
      const res = await api.get(`/api/frontier?subject_id=${subjectId}`);
      setData(res.data);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const diffLabel = (d: number) =>
    d <= 1 ? "Foundational" : d <= 2 ? "Intermediate" : "Advanced";

  return (
    <div className="h-full min-h-0 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Compass className="h-6 w-6" /> Knowledge Frontier
          <span className="text-xs font-normal text-muted-foreground ml-2">
            Your Zone of Proximal Development
          </span>
        </h1>
        <Tabs value={selectedSubject || ""} onValueChange={setSelectedSubject}>
          <TabsList>
            {subjects.map((s) => (
              <TabsTrigger key={s.id} value={s.id}>
                {s.code}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : !data ? (
        <div className="flex items-center justify-center text-muted-foreground py-24">
          No concept data available.
        </div>
      ) : (
        <>
          {/* Next best recommendation */}
          {data.next_best && (
            <Card className="border-l-4 border-primary bg-primary/5">
              <CardContent className="pt-4 flex items-center gap-3">
                <Rocket className="h-6 w-6 text-primary shrink-0" />
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Learning GPS — study this next
                  </p>
                  <p className="text-lg font-bold">{data.next_best.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {diffLabel(data.next_best.difficulty)} •{" "}
                    {Math.round((data.next_best.prereq_readiness || 0) * 100)}% prerequisite
                    readiness • all prerequisites met
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Progress bar */}
          <div className="flex h-3 rounded-full overflow-hidden bg-muted">
            <div
              className="bg-emerald-500"
              style={{ width: `${(data.counts.mastered / data.counts.total) * 100}%` }}
              title={`${data.counts.mastered} mastered`}
            />
            <div
              className="bg-blue-500"
              style={{ width: `${(data.counts.frontier / data.counts.total) * 100}%` }}
              title={`${data.counts.frontier} ready`}
            />
            <div
              className="bg-muted-foreground/30"
              style={{ width: `${(data.counts.locked / data.counts.total) * 100}%` }}
              title={`${data.counts.locked} locked`}
            />
          </div>

          {/* Three columns */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Frontier (ZPD) */}
            <Card className="border-blue-500/40">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-blue-500">
                  <Star className="h-4 w-4" /> Ready to Learn ({data.counts.frontier})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {data.frontier.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    Nothing unlocked right now.
                  </p>
                )}
                {data.frontier.map((c, i) => (
                  <div
                    key={c.id}
                    className="p-2 rounded-md border bg-blue-500/5 text-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{c.name}</span>
                      {i === 0 && (
                        <span className="text-[10px] bg-blue-500 text-white px-1.5 py-0.5 rounded-full">
                          BEST
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {c.chapter || diffLabel(c.difficulty)} •{" "}
                      {Math.round((c.prereq_readiness || 0) * 100)}% ready
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Mastered */}
            <Card className="border-emerald-500/40">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-emerald-500">
                  <CheckCircle2 className="h-4 w-4" /> Mastered ({data.counts.mastered})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {data.mastered.length === 0 && (
                  <p className="text-sm text-muted-foreground">Nothing mastered yet.</p>
                )}
                {data.mastered.map((c) => (
                  <div
                    key={c.id}
                    className="p-2 rounded-md border bg-emerald-500/5 text-sm flex items-center justify-between"
                  >
                    <span>{c.name}</span>
                    <span className="text-xs text-emerald-600 dark:text-emerald-400">
                      {Math.round(c.mastery * 100)}%
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Locked */}
            <Card className="border-muted">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
                  <Lock className="h-4 w-4" /> Locked ({data.counts.locked})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {data.locked.length === 0 && (
                  <p className="text-sm text-muted-foreground">Nothing locked.</p>
                )}
                {data.locked.map((c) => (
                  <div key={c.id} className="p-2 rounded-md border text-sm">
                    <span className="font-medium">{c.name}</span>
                    {c.missing_prerequisites && c.missing_prerequisites.length > 0 && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Needs:{" "}
                        {c.missing_prerequisites.map((p) => p.name).join(", ")}
                      </p>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
