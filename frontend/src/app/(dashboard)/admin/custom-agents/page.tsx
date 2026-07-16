"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Loader2, Bot, Plus, Trash2, Edit2, Save } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import api from "@/lib/api";

interface CustomAgent {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  rubric: Record<string, unknown>;
  created_at: string;
}

export default function CustomAgentsPage() {
  const { data: session } = useSession();
  const [agents, setAgents] = useState<CustomAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");

  useEffect(() => {
    if (session?.accessToken) loadAgents();
  }, [session?.accessToken]);

  const loadAgents = async () => {
    try {
      const res = await api.get("/api/custom-agents");
      setAgents(res.data);
    } catch {}
    setLoading(false);
  };

  const handleCreate = async () => {
    if (!name.trim() || !systemPrompt.trim()) return;
    try {
      await api.post("/api/custom-agents", {
        name,
        description: description || null,
        system_prompt: systemPrompt,
      });
      resetForm();
      await loadAgents();
    } catch {}
  };

  const handleUpdate = async (id: string) => {
    try {
      await api.put(`/api/custom-agents/${id}`, {
        name: name || undefined,
        description,
        system_prompt: systemPrompt || undefined,
      });
      setEditingId(null);
      resetForm();
      await loadAgents();
    } catch {}
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/custom-agents/${id}`);
      await loadAgents();
    } catch {}
  };

  const startEdit = (agent: CustomAgent) => {
    setEditingId(agent.id);
    setName(agent.name);
    setDescription(agent.description || "");
    setSystemPrompt(agent.system_prompt);
    setShowCreate(false);
  };

  const resetForm = () => {
    setName("");
    setDescription("");
    setSystemPrompt("");
    setShowCreate(false);
    setEditingId(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Bot className="h-6 w-6" /> Custom Agent Builder
        </h1>
        <Button onClick={() => { resetForm(); setShowCreate(!showCreate); }}>
          <Plus className="h-4 w-4 mr-1" /> New Agent
        </Button>
      </div>

      {/* Create/Edit Form */}
      {(showCreate || editingId) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              {editingId ? "Edit Agent" : "Create Custom Agent"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium">Name</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Lab Report Reviewer"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Description</label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description of what this agent does"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">System Prompt</label>
              <Textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="You are an expert at reviewing lab reports. Check for methodology, results analysis, and proper citations..."
                rows={6}
                className="mt-1 font-mono text-xs"
              />
            </div>
            <div className="flex gap-2">
              {editingId ? (
                <Button onClick={() => handleUpdate(editingId)}>
                  <Save className="h-4 w-4 mr-1" /> Save Changes
                </Button>
              ) : (
                <Button onClick={handleCreate} disabled={!name.trim() || !systemPrompt.trim()}>
                  <Plus className="h-4 w-4 mr-1" /> Create Agent
                </Button>
              )}
              <Button variant="ghost" onClick={resetForm}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Agent list */}
      {agents.length === 0 && !showCreate ? (
        <div className="flex-1 flex items-center justify-center text-center text-muted-foreground">
          <div>
            <Bot className="h-12 w-12 mx-auto mb-4 opacity-30" />
            <p className="text-lg font-medium">No custom agents yet</p>
            <p className="text-sm">Create agents with custom prompts and rubrics for specific assessment needs.</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {agents.map((agent) => (
            <Card key={agent.id}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Bot className="h-4 w-4 text-primary" />
                    {agent.name}
                  </span>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => startEdit(agent)}
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive"
                      onClick={() => handleDelete(agent.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {agent.description && (
                  <p className="text-xs text-muted-foreground mb-2">{agent.description}</p>
                )}
                <div className="bg-muted rounded p-2">
                  <p className="text-[10px] text-muted-foreground mb-1 font-medium">SYSTEM PROMPT</p>
                  <p className="text-xs font-mono line-clamp-3">{agent.system_prompt}</p>
                </div>
                <p className="text-[10px] text-muted-foreground mt-2">
                  Created: {new Date(agent.created_at).toLocaleDateString()}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
