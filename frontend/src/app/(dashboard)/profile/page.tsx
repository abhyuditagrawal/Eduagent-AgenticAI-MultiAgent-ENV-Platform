"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Loader2, Download, User, BookOpen, Calendar, BarChart3 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import api from "@/lib/api";
import { toast } from "sonner";

interface EnrolledSubject {
  id: string;
  name: string;
  code: string;
}

interface ActivityTotals {
  total_messages: number;
  total_concepts_mastered: number;
  total_study_hours: number;
}

interface StreakInfo {
  current: number;
  longest: number;
  total_days_active: number;
}

export default function ProfilePage() {
  const { data: session } = useSession();
  const [subjects, setSubjects] = useState<EnrolledSubject[]>([]);
  const [totals, setTotals] = useState<ActivityTotals | null>(null);
  const [streak, setStreak] = useState<StreakInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (session?.accessToken) loadData();
  }, [session?.accessToken]);

  const loadData = async () => {
    try {
      const [subjRes, actRes] = await Promise.all([
        api.get("/api/subjects/enrolled"),
        api.get("/api/dashboard/activity?days=365"),
      ]);
      setSubjects(subjRes.data);
      setTotals(actRes.data.totals);
      setStreak(actRes.data.streak);
    } catch {
      // Silently handle
    } finally {
      setLoading(false);
    }
  };

  const handleExportData = async () => {
    try {
      const [actRes, ...masteryResults] = await Promise.all([
        api.get("/api/dashboard/activity?days=365"),
        ...subjects.map((s) => api.get(`/api/dashboard/mastery?subject_id=${s.id}`)),
      ]);

      const exportData = {
        user: {
          name: session?.user?.name,
          email: session?.user?.email,
          exported_at: new Date().toISOString(),
        },
        activity: actRes.data,
        mastery: masteryResults.map((r) => r.data),
      };

      const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `eduagent-data-${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Data exported successfully");
    } catch {
      toast.error("Failed to export data");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      {/* User info */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
              <User className="h-8 w-8 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-semibold">{session?.user?.name}</h2>
              <p className="text-sm text-muted-foreground">{session?.user?.email}</p>
              <Badge variant="outline" className="mt-1 text-xs">
                {(session?.user as { role?: string })?.role || "student"}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Enrolled subjects */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              Enrolled Subjects
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          {subjects.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No subjects enrolled yet.
            </p>
          ) : (
            <div className="space-y-2">
              {subjects.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between py-2 px-3 rounded-lg bg-muted/50"
                >
                  <div>
                    <p className="text-sm font-medium">{s.name}</p>
                    <p className="text-xs text-muted-foreground">{s.code}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Study stats */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Study Statistics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-3 rounded-lg bg-muted/50">
              <p className="text-2xl font-bold">{totals?.total_messages || 0}</p>
              <p className="text-xs text-muted-foreground">Messages</p>
            </div>
            <div className="text-center p-3 rounded-lg bg-muted/50">
              <p className="text-2xl font-bold">{totals?.total_concepts_mastered || 0}</p>
              <p className="text-xs text-muted-foreground">Mastered</p>
            </div>
            <div className="text-center p-3 rounded-lg bg-muted/50">
              <p className="text-2xl font-bold">{totals?.total_study_hours || 0}</p>
              <p className="text-xs text-muted-foreground">Hours</p>
            </div>
            <div className="text-center p-3 rounded-lg bg-muted/50">
              <p className="text-2xl font-bold">{streak?.current || 0}</p>
              <p className="text-xs text-muted-foreground">Day Streak</p>
            </div>
          </div>
          {streak && (
            <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
              <span>Best streak: {streak.longest} days</span>
              <span>Active days: {streak.total_days_active}</span>
            </div>
          )}
        </CardContent>
      </Card>

      <Separator />

      {/* Export */}
      <Button variant="outline" className="w-full" onClick={handleExportData}>
        <Download className="h-4 w-4 mr-2" />
        Export My Data (JSON)
      </Button>
    </div>
  );
}
