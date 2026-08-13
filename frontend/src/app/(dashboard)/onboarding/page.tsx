"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Check, ChevronRight, GraduationCap, Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { toast } from "sonner";

interface SubjectData {
  id: string;
  name: string;
  code: string;
  description: string | null;
}

export default function OnboardingPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [subjects, setSubjects] = useState<SubjectData[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState(false);

  useEffect(() => {
    if (session?.accessToken) loadSubjects();
  }, [session?.accessToken]);

  const loadSubjects = async () => {
    try {
      const res = await api.get("/api/subjects");
      setSubjects(res.data);
    } catch {
      toast.error("Failed to load subjects");
    } finally {
      setLoading(false);
    }
  };

  const toggleSubject = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const handleEnroll = async () => {
    if (selected.size === 0) return;
    setEnrolling(true);
    try {
      for (const subjectId of selected) {
        await api.post(`/api/subjects/${subjectId}/enroll`);
      }
      toast.success(`Enrolled in ${selected.size} subject(s)`);
      setStep(2);
    } catch {
      toast.error("Failed to enroll");
    } finally {
      setEnrolling(false);
    }
  };

  const handleFinish = () => {
    router.push("/dashboard");
  };

  return (
    <div className="flex items-center justify-center h-full p-6">
      <div className="max-w-xl w-full space-y-6">
        {/* Progress */}
        <div className="flex items-center gap-2 justify-center">
          {[1, 2].map((s) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                  step >= s
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {step > s ? <Check className="h-4 w-4" /> : s}
              </div>
              {s < 2 && (
                <div
                  className={`w-12 h-0.5 ${step > s ? "bg-primary" : "bg-muted"}`}
                />
              )}
            </div>
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-4">
            <div className="text-center space-y-2">
              <GraduationCap className="h-12 w-12 mx-auto text-primary" />
              <h2 className="text-2xl font-semibold">Welcome to EduAgent!</h2>
              <p className="text-muted-foreground">
                Select the subjects you&apos;re studying this semester.
              </p>
            </div>

            {loading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : subjects.length === 0 ? (
              <Card>
                <CardContent className="p-6 text-center space-y-3">
                  <p className="text-sm text-muted-foreground">
                    No subjects yet. Add the subjects you&apos;re studying and
                    upload your own notes — that material is what your agents
                    will learn from.
                  </p>
                  <Button onClick={() => router.push("/my-subjects")}>
                    Add My First Subject
                    <ChevronRight className="h-4 w-4 ml-1" />
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {subjects.map((subject) => (
                  <Card
                    key={subject.id}
                    className={`cursor-pointer transition-all ${
                      selected.has(subject.id)
                        ? "ring-2 ring-primary bg-primary/5"
                        : "hover:bg-muted/50"
                    }`}
                    onClick={() => toggleSubject(subject.id)}
                  >
                    <CardContent className="p-4 flex items-center justify-between">
                      <div>
                        <p className="font-medium">{subject.name}</p>
                        <p className="text-xs text-muted-foreground">{subject.code}</p>
                      </div>
                      {selected.has(subject.id) && (
                        <Check className="h-5 w-5 text-primary" />
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {subjects.length > 0 && (
              <div className="space-y-2">
                <Button
                  className="w-full"
                  onClick={handleEnroll}
                  disabled={selected.size === 0 || enrolling}
                >
                  {enrolling ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : null}
                  Continue
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
                <Button
                  variant="ghost"
                  className="w-full text-sm"
                  onClick={() => router.push("/my-subjects")}
                >
                  Add a different subject instead
                </Button>
              </div>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="text-center space-y-6">
            <div className="p-4 rounded-full bg-green-100 dark:bg-green-900 w-fit mx-auto">
              <Check className="h-12 w-12 text-green-600" />
            </div>
            <div className="space-y-2">
              <h2 className="text-2xl font-semibold">You&apos;re all set!</h2>
              <p className="text-muted-foreground">
                Head to your dashboard to see your progress, or start chatting with your AI agents.
              </p>
            </div>
            <div className="flex gap-3 justify-center">
              <Button onClick={handleFinish}>Go to Dashboard</Button>
              <Button variant="outline" onClick={() => router.push("/chat")}>
                Start Chatting
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
