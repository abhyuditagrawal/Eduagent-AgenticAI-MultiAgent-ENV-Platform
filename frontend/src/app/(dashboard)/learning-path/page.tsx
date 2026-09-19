"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Loader2, TrendingUp, BookOpen, Brain, Trophy, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import api from "@/lib/api";

interface LearningEvent {
  id: string;
  event_type: string;
  concept_id: string | null;
  subject_id: string | null;
  agent_type: string | null;
  data: Record<string, unknown>;
  created_at: string;
}

const EVENT_ICONS: Record<string, typeof BookOpen> = {
  concept_learned: BookOpen,
  concept_reviewed: Brain,
  mastery_achieved: Trophy,
  weak_point_identified: AlertCircle,
  default: TrendingUp,
};

const EVENT_COLORS: Record<string, string> = {
  concept_learned: "bg-blue-500",
  concept_reviewed: "bg-purple-500",
  mastery_achieved: "bg-green-500",
  weak_point_identified: "bg-red-500",
  default: "bg-gray-500",
};

export default function LearningPathPage() {
  const { data: session } = useSession();
  const [events, setEvents] = useState<LearningEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (session?.accessToken) loadEvents();
  }, [session?.accessToken]);

  const loadEvents = async () => {
    try {
      const res = await api.get("/api/analytics/learning-path");
      setEvents(res.data);
    } catch {}
    setLoading(false);
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  };

  const groupByDate = (events: LearningEvent[]) => {
    const groups: Record<string, LearningEvent[]> = {};
    for (const e of events) {
      const date = new Date(e.created_at).toLocaleDateString("en-US", {
        month: "long", day: "numeric", year: "numeric",
      });
      if (!groups[date]) groups[date] = [];
      groups[date].push(e);
    }
    return groups;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const grouped = groupByDate(events);

  return (
    <div className="h-full min-h-0 overflow-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2">
        <TrendingUp className="h-6 w-6" /> Learning Path
      </h1>

      {events.length === 0 ? (
        <div className="flex items-center justify-center text-center text-muted-foreground py-24">
          <div>
            <TrendingUp className="h-12 w-12 mx-auto mb-4 opacity-30" />
            <p className="text-lg font-medium">Your learning journey starts here</p>
            <p className="text-sm">Start studying and your progress will appear as a timeline.</p>
          </div>
        </div>
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-border" />

          {Object.entries(grouped).map(([date, dayEvents]) => (
            <div key={date} className="mb-8">
              <div className="sticky top-0 z-10 bg-background/95 backdrop-blur py-2 pl-12 mb-3">
                <h3 className="text-sm font-semibold text-muted-foreground">{date}</h3>
              </div>

              {dayEvents.map((event) => {
                const Icon = EVENT_ICONS[event.event_type] || EVENT_ICONS.default;
                const dotColor = EVENT_COLORS[event.event_type] || EVENT_COLORS.default;

                return (
                  <div key={event.id} className="relative flex items-start gap-4 mb-4 pl-1">
                    <div className={`w-7 h-7 rounded-full ${dotColor} flex items-center justify-center shrink-0 z-10`}>
                      <Icon className="h-3.5 w-3.5 text-white" />
                    </div>
                    <Card className="flex-1">
                      <CardContent className="py-3 px-4">
                        <div className="flex justify-between items-start">
                          <div>
                            <p className="text-sm font-medium">
                              {event.event_type.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
                            </p>
                            {event.agent_type && (
                              <p className="text-xs text-muted-foreground">
                                via {event.agent_type} agent
                              </p>
                            )}
                            {event.data && Object.keys(event.data).length > 0 && (
                              <p className="text-xs text-muted-foreground mt-1">
                                {event.data.concept_name ? `Concept: ${String(event.data.concept_name)}` : ""}
                                {event.data.confidence ? ` — Confidence: ${Math.round(Number(event.data.confidence) * 100)}%` : ""}
                              </p>
                            )}
                          </div>
                          <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                            {new Date(event.created_at).toLocaleTimeString("en-US", {
                              hour: "2-digit", minute: "2-digit",
                            })}
                          </span>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
