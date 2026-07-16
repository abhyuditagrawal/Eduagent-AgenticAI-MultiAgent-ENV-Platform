"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Loader2, Brain, AlertTriangle, TrendingDown, Activity } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import api from "@/lib/api";

interface SubjectInfo {
  id: string;
  name: string;
  code: string;
}

interface MasteryRow {
  concept_id: string;
  concept_name: string;
  chapter: string | null;
  difficulty: number;
  bkt_mastery: number;
  current_recall: number;
  memory_stability_days: number;
  predicted_forget_at: string | null;
  days_until_forget: number | null;
  at_risk: boolean;
}

interface ForecastDay {
  day_offset: number;
  date: string;
  concepts: string[];
  count: number;
}

export default function KnowledgeTracingPage() {
  const { data: session } = useSession();
  const [subjects, setSubjects] = useState<SubjectInfo[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [mastery, setMastery] = useState<MasteryRow[]>([]);
  const [timeline, setTimeline] = useState<ForecastDay[]>([]);
  const [atRiskNow, setAtRiskNow] = useState<MasteryRow[]>([]);
  const [avgMastery, setAvgMastery] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (session?.accessToken) loadSubjects();
  }, [session?.accessToken]);

  useEffect(() => {
    if (selectedSubject) loadData(selectedSubject);
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

  const loadData = async (subjectId: string) => {
    setLoading(true);
    try {
      const [m, f] = await Promise.all([
        api.get(`/api/knowledge-tracing/mastery?subject_id=${subjectId}`),
        api.get(`/api/knowledge-tracing/forgetting-forecast?subject_id=${subjectId}`),
      ]);
      setMastery(m.data);
      setTimeline(f.data.timeline || []);
      setAtRiskNow(f.data.at_risk_now || []);
      setAvgMastery(f.data.avg_mastery || 0);
    } catch {
      setMastery([]);
      setTimeline([]);
      setAtRiskNow([]);
    } finally {
      setLoading(false);
    }
  };

  const masteryColor = (v: number) =>
    v >= 0.8 ? "#22c55e" : v >= 0.5 ? "#eab308" : v >= 0.25 ? "#f97316" : "#ef4444";

  const chartData = mastery
    .slice()
    .sort((a, b) => a.bkt_mastery - b.bkt_mastery)
    .slice(0, 15)
    .map((m) => ({
      name: m.concept_name.length > 18 ? m.concept_name.slice(0, 18) + "…" : m.concept_name,
      mastery: Math.round(m.bkt_mastery * 100),
      recall: Math.round(m.current_recall * 100),
    }));

  return (
    <div className="flex flex-col h-full overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Brain className="h-6 w-6" /> Knowledge Tracing
          <span className="text-xs font-normal text-muted-foreground ml-2">
            Bayesian mastery &amp; predictive forgetting
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
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
                  <Activity className="h-4 w-4" /> Avg BKT Mastery
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">{Math.round(avgMastery * 100)}%</p>
                <p className="text-xs text-muted-foreground">
                  Probability skills are truly learned
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
                  <AlertTriangle className="h-4 w-4" /> At Risk Now
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-red-500">{atRiskNow.length}</p>
                <p className="text-xs text-muted-foreground">
                  Recall below 50% — review recommended
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
                  <TrendingDown className="h-4 w-4" /> Concepts Tracked
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">{mastery.length}</p>
                <p className="text-xs text-muted-foreground">
                  Modelled with a Hidden Markov Model
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Mastery bar chart */}
          {chartData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  Mastery vs. Current Recall (weakest 15)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} layout="vertical" margin={{ left: 40 }}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                      <XAxis type="number" domain={[0, 100]} unit="%" fontSize={11} />
                      <YAxis
                        type="category"
                        dataKey="name"
                        width={120}
                        fontSize={10}
                      />
                      <Tooltip />
                      <Bar dataKey="mastery" name="BKT Mastery %" radius={[0, 4, 4, 0]}>
                        {chartData.map((d, i) => (
                          <Cell key={i} fill={masteryColor(d.mastery / 100)} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Forgetting forecast timeline */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <TrendingDown className="h-4 w-4" /> Predictive Forgetting Forecast
              </CardTitle>
            </CardHeader>
            <CardContent>
              {timeline.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No concepts predicted to drop below the retention threshold in the
                  next two weeks. Keep it up!
                </p>
              ) : (
                <div className="space-y-2">
                  {timeline.map((day) => (
                    <div
                      key={day.day_offset}
                      className="flex items-start gap-3 border-l-2 border-orange-400 pl-3 py-1"
                    >
                      <div className="text-xs font-mono text-muted-foreground w-24 shrink-0">
                        {day.day_offset === 0 ? "Today" : `+${day.day_offset}d`}
                        <div className="opacity-60">{day.date}</div>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {day.concepts.map((c, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300 text-xs"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
