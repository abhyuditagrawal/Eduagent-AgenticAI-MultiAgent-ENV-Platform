"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  Loader2,
  Dna,
  RefreshCw,
  Gauge,
  Clock,
  Repeat,
  Lightbulb,
  AlertCircle,
  Sparkles,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { toast } from "sonner";

interface Genome {
  pace_label: string;
  pace_score: number;
  preferred_modality: string;
  preferred_modality_label: string;
  optimal_hour: number;
  persistence_score: number;
  avg_session_minutes: number;
  misconception_patterns: string[];
  strengths: string[];
  summary: string;
  data_points: number;
  updated_at: string | null;
}

export default function LearningGenomePage() {
  const { data: session } = useSession();
  const [genome, setGenome] = useState<Genome | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (session?.accessToken) load();
  }, [session?.accessToken]);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/api/genome");
      setGenome(res.data);
    } catch {
      setGenome(null);
    } finally {
      setLoading(false);
    }
  };

  const refresh = async () => {
    setRefreshing(true);
    try {
      const res = await api.post("/api/genome/refresh");
      setGenome(res.data);
      toast.success("Learning genome recomputed");
    } catch {
      toast.error("Failed to refresh genome");
    } finally {
      setRefreshing(false);
    }
  };

  const paceColor =
    genome?.pace_label === "fast"
      ? "text-emerald-500"
      : genome?.pace_label === "slow"
      ? "text-orange-500"
      : "text-blue-500";

  const fmtHour = (h: number) => {
    const period = h >= 12 ? "PM" : "AM";
    const hr = h % 12 === 0 ? 12 : h % 12;
    return `${hr}:00 ${period}`;
  };

  return (
    <div className="flex flex-col h-full overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Dna className="h-6 w-6" /> Learning Genome
          <span className="text-xs font-normal text-muted-foreground ml-2">
            Your evolving cognitive fingerprint
          </span>
        </h1>
        <Button onClick={refresh} disabled={refreshing} variant="outline">
          {refreshing ? (
            <Loader2 className="h-4 w-4 animate-spin mr-1" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-1" />
          )}
          Recompute
        </Button>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : !genome ? (
        <div className="flex-1 flex items-center justify-center text-center text-muted-foreground">
          <div>
            <Dna className="h-12 w-12 mx-auto mb-4 opacity-30" />
            <p className="text-lg font-medium">No genome yet</p>
            <p className="text-sm">Chat with the agents, then recompute to build your profile.</p>
          </div>
        </div>
      ) : (
        <>
          {/* AI summary */}
          {genome.summary && (
            <Card className="border-l-4 border-primary bg-primary/5">
              <CardContent className="pt-4 flex gap-3">
                <Sparkles className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                <p className="text-sm leading-relaxed">{genome.summary}</p>
              </CardContent>
            </Card>
          )}

          {/* Stat grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
                  <Gauge className="h-4 w-4" /> Learning Pace
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className={`text-2xl font-bold capitalize ${paceColor}`}>
                  {genome.pace_label}
                </p>
                <p className="text-xs text-muted-foreground">
                  Score {Math.round(genome.pace_score * 100)}/100
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
                  <Sparkles className="h-4 w-4" /> Preferred Mode
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-lg font-semibold capitalize">
                  {genome.preferred_modality_label}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
                  <Clock className="h-4 w-4" /> Peak Hour
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{fmtHour(genome.optimal_hour)}</p>
                <p className="text-xs text-muted-foreground">Most active study time</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
                  <Repeat className="h-4 w-4" /> Persistence
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">
                  {Math.round(genome.persistence_score * 100)}%
                </p>
                <p className="text-xs text-muted-foreground">Revisits weak topics</p>
              </CardContent>
            </Card>
          </div>

          {/* Strengths + misconceptions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-emerald-500">
                  <Lightbulb className="h-4 w-4" /> Strengths
                </CardTitle>
              </CardHeader>
              <CardContent>
                {genome.strengths.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Keep learning — strengths will emerge.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {genome.strengths.map((s, i) => (
                      <li key={i} className="text-sm flex gap-2">
                        <span className="text-emerald-500">✓</span>
                        {s}
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-orange-500">
                  <AlertCircle className="h-4 w-4" /> Misconception Patterns
                </CardTitle>
              </CardHeader>
              <CardContent>
                {genome.misconception_patterns.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No recurring misconceptions detected.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {genome.misconception_patterns.map((m, i) => (
                      <li key={i} className="text-sm flex gap-2">
                        <span className="text-orange-500">!</span>
                        {m}
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          <p className="text-xs text-muted-foreground">
            Derived from {genome.data_points} interactions
            {genome.updated_at
              ? ` • updated ${new Date(genome.updated_at).toLocaleString()}`
              : ""}
            . This profile is injected into every agent so responses adapt to you.
          </p>
        </>
      )}
    </div>
  );
}
