"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Loader2, BarChart3, Users, Zap, AlertTriangle, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import api from "@/lib/api";

interface AgentStat {
  agent_type: string;
  total_invocations: number;
  avg_response_time_ms: number;
  success_rate: number;
}

interface IntentStat {
  intent: string;
  count: number;
}

interface AgentAnalytics {
  period_days: number;
  total_invocations: number;
  unique_students: number;
  avg_response_time_ms: number;
  agent_stats: AgentStat[];
  intent_distribution: IntentStat[];
  daily_volume: { date: string; requests: number }[];
}

interface WeakConcept {
  concept: string;
  subject: string;
  avg_confidence: number;
  students_struggling: number;
}

interface ClassAnalytics {
  total_students: number;
  total_interactions: number;
  subjects: {
    subject_name: string;
    subject_code: string;
    enrolled_students: number;
    avg_mastery: number;
  }[];
  top_weak_concepts: WeakConcept[];
}

export default function AdminAnalyticsPage() {
  const { data: session } = useSession();
  const [agentData, setAgentData] = useState<AgentAnalytics | null>(null);
  const [classData, setClassData] = useState<ClassAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (session?.accessToken) loadData();
  }, [session?.accessToken]);

  const loadData = async () => {
    try {
      const [agentRes, classRes] = await Promise.all([
        api.get("/api/analytics/agents?days=30"),
        api.get("/api/analytics/class"),
      ]);
      setAgentData(agentRes.data);
      setClassData(classRes.data);
    } catch {}
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="h-full min-h-0 overflow-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2">
        <BarChart3 className="h-6 w-6" /> Platform Analytics
      </h1>

      {/* Top stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4 text-center">
            <Users className="h-5 w-5 mx-auto mb-1 text-blue-500" />
            <p className="text-2xl font-bold">{classData?.total_students || 0}</p>
            <p className="text-xs text-muted-foreground">Total Students</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <Zap className="h-5 w-5 mx-auto mb-1 text-yellow-500" />
            <p className="text-2xl font-bold">{agentData?.total_invocations || 0}</p>
            <p className="text-xs text-muted-foreground">Agent Invocations (30d)</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <TrendingUp className="h-5 w-5 mx-auto mb-1 text-green-500" />
            <p className="text-2xl font-bold">{agentData?.unique_students || 0}</p>
            <p className="text-xs text-muted-foreground">Active Students (30d)</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <BarChart3 className="h-5 w-5 mx-auto mb-1 text-purple-500" />
            <p className="text-2xl font-bold">{agentData?.avg_response_time_ms || 0}ms</p>
            <p className="text-xs text-muted-foreground">Avg Response Time</p>
          </CardContent>
        </Card>
      </div>

      {/* Agent Performance */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Agent Performance</CardTitle>
        </CardHeader>
        <CardContent>
          {agentData?.agent_stats && agentData.agent_stats.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-2 font-medium">Agent</th>
                    <th className="pb-2 font-medium text-right">Invocations</th>
                    <th className="pb-2 font-medium text-right">Avg Time</th>
                    <th className="pb-2 font-medium text-right">Success Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {agentData.agent_stats.map((stat) => (
                    <tr key={stat.agent_type} className="border-b last:border-0">
                      <td className="py-2 capitalize">{stat.agent_type.replace(/_/g, " ")}</td>
                      <td className="py-2 text-right">{stat.total_invocations}</td>
                      <td className="py-2 text-right">{stat.avg_response_time_ms}ms</td>
                      <td className="py-2 text-right">
                        <span className={stat.success_rate >= 95 ? "text-green-600" : "text-yellow-600"}>
                          {stat.success_rate}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No agent data yet.</p>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Subject Mastery */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Class Mastery by Subject</CardTitle>
          </CardHeader>
          <CardContent>
            {classData?.subjects && classData.subjects.length > 0 ? (
              <div className="space-y-3">
                {classData.subjects.map((s) => (
                  <div key={s.subject_code}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium">{s.subject_code} — {s.subject_name}</span>
                      <span className="text-muted-foreground">{s.avg_mastery}%</span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all ${
                          s.avg_mastery >= 70 ? "bg-green-500" :
                          s.avg_mastery >= 40 ? "bg-yellow-500" : "bg-red-500"
                        }`}
                        style={{ width: `${Math.min(s.avg_mastery, 100)}%` }}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {s.enrolled_students} students enrolled
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No subject data yet.</p>
            )}
          </CardContent>
        </Card>

        {/* Top Weak Concepts */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-1">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              Top Weak Concepts (Class-wide)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {classData?.top_weak_concepts && classData.top_weak_concepts.length > 0 ? (
              <div className="space-y-2">
                {classData.top_weak_concepts.slice(0, 10).map((w, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <div>
                      <span className="font-medium">{w.concept}</span>
                      <span className="text-xs text-muted-foreground ml-2">({w.subject})</span>
                    </div>
                    <div className="text-right">
                      <span className="text-red-500 font-medium">{w.avg_confidence}%</span>
                      <span className="text-xs text-muted-foreground ml-1">
                        ({w.students_struggling} students)
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No weak concepts data yet.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Intent Distribution */}
      {agentData?.intent_distribution && agentData.intent_distribution.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Intent Distribution (30 days)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              {agentData.intent_distribution.map((intent) => {
                const total = agentData.total_invocations || 1;
                const pct = Math.round((intent.count / total) * 100);
                return (
                  <div key={intent.intent} className="bg-muted rounded-lg px-3 py-2 text-center">
                    <p className="text-lg font-bold">{pct}%</p>
                    <p className="text-xs text-muted-foreground capitalize">
                      {intent.intent.replace(/_/g, " ")}
                    </p>
                    <p className="text-[10px] text-muted-foreground">{intent.count} queries</p>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
