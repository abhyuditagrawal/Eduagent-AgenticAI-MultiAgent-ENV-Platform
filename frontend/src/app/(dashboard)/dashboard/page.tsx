"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MasteryHeatmap } from "@/components/dashboard/mastery-heatmap";
import { ExamReadiness } from "@/components/dashboard/exam-readiness";
import { WeakPointsList } from "@/components/dashboard/weak-points-list";
import { ActivityTimeline } from "@/components/dashboard/activity-timeline";
import { ActivityChart } from "@/components/dashboard/activity-chart";
import api from "@/lib/api";

interface SubjectInfo {
  id: string;
  name: string;
  code: string;
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [subjects, setSubjects] = useState<SubjectInfo[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Data states
  const [mastery, setMastery] = useState<Record<string, unknown> | null>(null);
  const [weakPoints, setWeakPoints] = useState<Record<string, unknown> | null>(null);
  const [examReadiness, setExamReadiness] = useState<Record<string, unknown> | null>(null);
  const [activity, setActivity] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (session?.accessToken) loadSubjects();
  }, [session?.accessToken]);

  useEffect(() => {
    if (selectedSubject) loadDashboardData(selectedSubject);
  }, [selectedSubject]);

  const loadSubjects = async () => {
    try {
      const res = await api.get("/api/subjects/enrolled");
      const enrolled = res.data;
      setSubjects(enrolled);
      if (enrolled.length > 0) {
        setSelectedSubject(enrolled[0].id);
      } else {
        setLoading(false);
      }
    } catch {
      setLoading(false);
    }
  };

  const loadDashboardData = async (subjectId: string) => {
    setLoading(true);
    try {
      const [masteryRes, weakRes, examRes, activityRes] = await Promise.all([
        api.get(`/api/dashboard/mastery?subject_id=${subjectId}`),
        api.get(`/api/dashboard/weak-points?subject_id=${subjectId}`),
        api.get(`/api/dashboard/exam-readiness?subject_id=${subjectId}`),
        api.get("/api/dashboard/activity?days=30"),
      ]);
      setMastery(masteryRes.data);
      setWeakPoints(weakRes.data);
      setExamReadiness(examRes.data);
      setActivity(activityRes.data);
    } catch {
      // Silently handle
    } finally {
      setLoading(false);
    }
  };

  if (subjects.length === 0 && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center space-y-4 p-8">
        <h2 className="text-2xl font-semibold">No subjects enrolled</h2>
        <p className="text-muted-foreground max-w-md">
          Enroll in a subject to see your dashboard. Go to your profile or contact an admin.
        </p>
      </div>
    );
  }

  const overallScore = mastery
    ? Math.round(((mastery as { overall_score: number }).overall_score || 0) * 100)
    : 0;

  return (
    <div className="flex flex-col h-full overflow-auto">
      {/* Subject tabs */}
      <div className="border-b px-6 pt-4">
        <Tabs
          value={selectedSubject || ""}
          onValueChange={(v) => setSelectedSubject(v)}
        >
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
        <div className="flex-1 p-6 space-y-6 overflow-auto">
          {/* Top row: Overall score + Exam readiness */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Overall mastery */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Overall Mastery</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col items-center py-4">
                  <div className="relative">
                    <svg width="120" height="120" className="-rotate-90">
                      <circle
                        cx="60"
                        cy="60"
                        r="50"
                        fill="none"
                        stroke="currentColor"
                        className="text-muted/30"
                        strokeWidth="8"
                      />
                      <circle
                        cx="60"
                        cy="60"
                        r="50"
                        fill="none"
                        stroke={overallScore >= 80 ? "#22c55e" : overallScore >= 50 ? "#3b82f6" : "#f97316"}
                        strokeWidth="8"
                        strokeDasharray={2 * Math.PI * 50}
                        strokeDashoffset={2 * Math.PI * 50 * (1 - overallScore / 100)}
                        strokeLinecap="round"
                        className="transition-all duration-1000"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-2xl font-bold">{overallScore}%</span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    {(mastery as { chapters?: unknown[] })?.chapters
                      ? `${((mastery as { chapters: unknown[] }).chapters as unknown[]).reduce(
                          (sum: number, ch: unknown) => sum + ((ch as { concepts: unknown[] }).concepts?.length || 0),
                          0
                        )} concepts tracked`
                      : ""}
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Exam readiness */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Exam Readiness</CardTitle>
              </CardHeader>
              <CardContent>
                {examReadiness && (
                  <ExamReadiness
                    overallReadiness={(examReadiness as { overall_readiness: number }).overall_readiness}
                    readinessLabel={(examReadiness as { readiness_label: string }).readiness_label}
                    byDifficulty={
                      (examReadiness as { by_difficulty: { foundational: number; intermediate: number; advanced: number } }).by_difficulty
                    }
                    highRiskTopics={(examReadiness as { high_risk_topics: [] }).high_risk_topics}
                    strengths={(examReadiness as { strengths: [] }).strengths}
                    studyPlan={(examReadiness as { study_plan: [] }).study_plan}
                    recommendedHours={(examReadiness as { recommended_study_hours: number }).recommended_study_hours}
                  />
                )}
              </CardContent>
            </Card>

            {/* Activity */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Study Activity</CardTitle>
              </CardHeader>
              <CardContent>
                {activity && (
                  <ActivityTimeline
                    dailyActivity={(activity as { daily_activity: [] }).daily_activity}
                    streak={(activity as { streak: { current: number; longest: number; total_days_active: number } }).streak}
                    totals={
                      (activity as { totals: { total_messages: number; total_concepts_mastered: number; total_study_hours: number } }).totals
                    }
                  />
                )}
              </CardContent>
            </Card>
          </div>

          {/* Mastery heatmap */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Concept Mastery</CardTitle>
            </CardHeader>
            <CardContent>
              {mastery && (
                <MasteryHeatmap
                  chapters={(mastery as { chapters: [] }).chapters}
                />
              )}
            </CardContent>
          </Card>

          {/* Bottom row: Weak points + Activity chart */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Weak Points</CardTitle>
              </CardHeader>
              <CardContent>
                {weakPoints && (
                  <WeakPointsList
                    weakConcepts={(weakPoints as { weak_concepts: [] }).weak_concepts}
                    totalWeak={(weakPoints as { total_weak: number }).total_weak}
                    totalConcepts={(weakPoints as { total_concepts: number }).total_concepts}
                  />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Activity Over Time</CardTitle>
              </CardHeader>
              <CardContent>
                {activity && (
                  <ActivityChart
                    dailyActivity={(activity as { daily_activity: [] }).daily_activity}
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
