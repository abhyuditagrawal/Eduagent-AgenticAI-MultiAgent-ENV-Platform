"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Loader2 } from "lucide-react";
import { Tabs, TabsTrigger, TabsList } from "@/components/ui/tabs";
import { ConceptGraphView } from "@/components/dashboard/concept-graph-view";
import api from "@/lib/api";

interface SubjectInfo {
  id: string;
  name: string;
  code: string;
}

interface GraphNode {
  id: string;
  name: string;
  chapter: string | null;
  difficulty: number;
  confidence: number;
  status: string;
}

interface GraphEdge {
  source: string;
  target: string;
  strength: number;
}

export default function ConceptMapPage() {
  const { data: session } = useSession();
  const [subjects, setSubjects] = useState<SubjectInfo[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (session?.accessToken) loadSubjects();
  }, [session?.accessToken]);

  useEffect(() => {
    if (selectedSubject) loadGraph(selectedSubject);
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

  const loadGraph = async (subjectId: string) => {
    setLoading(true);
    try {
      const res = await api.get(`/api/dashboard/concept-graph?subject_id=${subjectId}`);
      setGraphNodes(res.data.nodes);
      setGraphEdges(res.data.edges);
    } catch {
      setGraphNodes([]);
      setGraphEdges([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="border-b px-6 pt-4 pb-2 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Concept Map</h1>
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

      <div className="flex-1 relative">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <ConceptGraphView nodes={graphNodes} edges={graphEdges} />
        )}
      </div>
    </div>
  );
}
