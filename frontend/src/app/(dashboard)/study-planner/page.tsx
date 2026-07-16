"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Loader2, CalendarDays, Clock, Target, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import api from "@/lib/api";

interface Task {
  topic: string;
  activity: string;
  duration_minutes: number;
}

interface DayPlan {
  day: number;
  date_label: string;
  focus: string;
  tasks: Task[];
  priority: string;
}

interface SubjectInfo {
  id: string;
  name: string;
  code: string;
}

export default function StudyPlannerPage() {
  const { data: session } = useSession();
  const [subjects, setSubjects] = useState<SubjectInfo[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [examDate, setExamDate] = useState("");
  const [hoursPerDay, setHoursPerDay] = useState("2");
  const [plan, setPlan] = useState<DayPlan[] | null>(null);
  const [masteryPct, setMasteryPct] = useState(0);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (session?.accessToken) loadSubjects();
  }, [session?.accessToken]);

  const loadSubjects = async () => {
    try {
      const res = await api.get("/api/subjects/enrolled");
      setSubjects(res.data);
      if (res.data.length > 0) setSelectedSubject(res.data[0].id);
    } catch {}
  };

  const generatePlan = async () => {
    if (!selectedSubject) return;
    setGenerating(true);
    try {
      const res = await api.post("/api/study-planner/generate", {
        subject_id: selectedSubject,
        exam_date: examDate || null,
        study_hours_per_day: parseFloat(hoursPerDay) || 2,
      });
      setPlan(res.data.plan);
      setMasteryPct(res.data.mastery_pct);
    } catch {}
    setGenerating(false);
  };

  const priorityColor = (p: string) => {
    if (p === "high") return "border-red-500 bg-red-500/5";
    if (p === "medium") return "border-yellow-500 bg-yellow-500/5";
    return "border-green-500 bg-green-500/5";
  };

  return (
    <div className="flex flex-col h-full overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <CalendarDays className="h-6 w-6" /> Smart Study Planner
        </h1>
      </div>

      {/* Configuration */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
              <label className="text-sm font-medium">Subject</label>
              <Tabs
                value={selectedSubject || ""}
                onValueChange={setSelectedSubject}
                className="mt-1"
              >
                <TabsList className="w-full">
                  {subjects.map((s) => (
                    <TabsTrigger key={s.id} value={s.id} className="text-xs">
                      {s.code}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
            </div>
            <div>
              <label className="text-sm font-medium">Exam Date (optional)</label>
              <Input
                type="date"
                value={examDate}
                onChange={(e) => setExamDate(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Hours/Day</label>
              <Input
                type="number"
                min="0.5"
                max="8"
                step="0.5"
                value={hoursPerDay}
                onChange={(e) => setHoursPerDay(e.target.value)}
                className="mt-1"
              />
            </div>
            <Button onClick={generatePlan} disabled={generating || !selectedSubject}>
              {generating ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1" />
              ) : (
                <Sparkles className="h-4 w-4 mr-1" />
              )}
              Generate Plan
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Plan display */}
      {plan && (
        <>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <Target className="h-4 w-4" /> Current mastery: {masteryPct}%
            </span>
            <span className="flex items-center gap-1">
              <CalendarDays className="h-4 w-4" /> {plan.length} days planned
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {plan.map((day) => (
              <Card key={day.day} className={`border-l-4 ${priorityColor(day.priority)}`}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex justify-between">
                    <span>{day.date_label}</span>
                    <span className="text-xs font-normal text-muted-foreground uppercase">
                      {day.priority}
                    </span>
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">{day.focus}</p>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {day.tasks.map((task, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                            task.activity === "review" ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" :
                            task.activity === "practice" ? "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300" :
                            "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                          }`}>
                            {task.activity}
                          </span>
                          <span className="truncate max-w-[150px]">{task.topic}</span>
                        </div>
                        <span className="text-muted-foreground flex items-center gap-0.5">
                          <Clock className="h-3 w-3" /> {task.duration_minutes}m
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}

      {!plan && !generating && (
        <div className="flex-1 flex items-center justify-center text-center text-muted-foreground">
          <div>
            <CalendarDays className="h-12 w-12 mx-auto mb-4 opacity-30" />
            <p className="text-lg font-medium">No study plan yet</p>
            <p className="text-sm">Configure your preferences and generate a personalized plan.</p>
          </div>
        </div>
      )}
    </div>
  );
}
