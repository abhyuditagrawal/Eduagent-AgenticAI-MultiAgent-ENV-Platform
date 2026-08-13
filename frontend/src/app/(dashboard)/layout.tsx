"use client";

import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  MessageSquare,
  Plus,
  Upload,
  LogOut,
  GraduationCap,
  Menu,
  ChevronLeft,
  LayoutDashboard,
  Network,
  User,
  BookOpen,
  Brain,
  CalendarDays,
  TrendingUp,
  Users,
  BarChart3,
  Bot,
  Activity,
  Swords,
  Dna,
  Compass,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { useChatStore, type Conversation } from "@/stores/chat-store";
import api from "@/lib/api";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { conversations, setConversations, setActiveConversation } =
    useChatStore();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    }
  }, [status, router]);

  useEffect(() => {
    if (session?.accessToken) {
      loadConversations();
    }
  }, [session?.accessToken]);

  const loadConversations = async () => {
    try {
      const res = await api.get("/api/chat/history");
      setConversations(res.data);
    } catch {
      // Silently fail on initial load
    }
  };

  const handleNewChat = () => {
    setActiveConversation(null);
    useChatStore.getState().setMessages([]);
    router.push("/chat");
  };

  const handleSelectConversation = async (conv: Conversation) => {
    setActiveConversation(conv);
    router.push("/chat");

    try {
      const res = await api.get(`/api/chat/conversations/${conv.id}`);
      useChatStore.getState().setMessages(res.data);
    } catch {
      // Handle error
    }
  };

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (status === "unauthenticated") return null;

  const initials = session?.user?.name
    ? session.user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
    : "U";

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? "w-72" : "w-0"
        } transition-all duration-300 bg-card border-r flex flex-col overflow-hidden`}
      >
        <div className="p-4 flex items-center gap-2">
          <GraduationCap className="h-6 w-6 text-primary shrink-0" />
          <span className="font-bold text-lg whitespace-nowrap">EduAgent</span>
          <div className="ml-auto flex items-center gap-0.5 shrink-0">
            <ThemeToggle />
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setSidebarOpen(false)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="px-3 pb-2 space-y-1">
          <Button
            className="w-full justify-start gap-2"
            onClick={handleNewChat}
          >
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
          <Link href="/dashboard">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-sm"
            >
              <LayoutDashboard className="h-4 w-4" />
              Dashboard
            </Button>
          </Link>
          <Link href="/my-subjects">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-sm"
            >
              <BookOpen className="h-4 w-4" />
              My Subjects
            </Button>
          </Link>
          <Link href="/concept-map">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-sm"
            >
              <Network className="h-4 w-4" />
              Concept Map
            </Button>
          </Link>
          <Link href="/knowledge-frontier">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-sm"
            >
              <Compass className="h-4 w-4" />
              Knowledge Frontier
            </Button>
          </Link>
          <Link href="/knowledge-tracing">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-sm"
            >
              <Activity className="h-4 w-4" />
              Knowledge Tracing
            </Button>
          </Link>
          <Link href="/debate">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-sm"
            >
              <Swords className="h-4 w-4" />
              Debate Arena
            </Button>
          </Link>
          <Link href="/learning-genome">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-sm"
            >
              <Dna className="h-4 w-4" />
              Learning Genome
            </Button>
          </Link>
          <Link href="/flashcards">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-sm"
            >
              <Brain className="h-4 w-4" />
              Flashcards
            </Button>
          </Link>
          <Link href="/study-planner">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-sm"
            >
              <CalendarDays className="h-4 w-4" />
              Study Planner
            </Button>
          </Link>
          <Link href="/learning-path">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-sm"
            >
              <TrendingUp className="h-4 w-4" />
              Learning Path
            </Button>
          </Link>
          <Link href="/study-groups">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-sm"
            >
              <Users className="h-4 w-4" />
              Study Groups
            </Button>
          </Link>
        </div>

        <Separator />

        <ScrollArea className="flex-1 px-3 py-2">
          <div className="space-y-1">
            {conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => handleSelectConversation(conv)}
                className="w-full text-left px-3 py-2 rounded-md hover:bg-accent text-sm truncate transition-colors"
              >
                <MessageSquare className="h-3.5 w-3.5 inline mr-2 opacity-60" />
                {conv.title || "New conversation"}
              </button>
            ))}
          </div>
        </ScrollArea>

        <Separator />

        <div className="p-3 space-y-1">
          <Link href="/profile">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-sm"
            >
              <User className="h-4 w-4" />
              Profile
            </Button>
          </Link>
          {session?.user?.role === "admin" && (
            <>
              <Link href="/admin/upload">
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-sm"
                >
                  <Upload className="h-4 w-4" />
                  Upload PDFs
                </Button>
              </Link>
              <Link href="/admin/subjects">
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-sm"
                >
                  <BookOpen className="h-4 w-4" />
                  Manage Subjects
                </Button>
              </Link>
              <Link href="/admin/analytics">
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-sm"
                >
                  <BarChart3 className="h-4 w-4" />
                  Analytics
                </Button>
              </Link>
              <Link href="/admin/custom-agents">
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-sm"
                >
                  <Bot className="h-4 w-4" />
                  Custom Agents
                </Button>
              </Link>
            </>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger
              className="w-full flex items-center gap-2 text-sm px-3 py-2 rounded-md hover:bg-accent transition-colors"
            >
              <Avatar className="h-6 w-6">
                <AvatarFallback className="text-xs">{initials}</AvatarFallback>
              </Avatar>
              <span className="truncate">{session?.user?.name}</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              <DropdownMenuItem
                className="text-destructive cursor-pointer"
                onClick={() => signOut({ callbackUrl: "/login" })}
              >
                <LogOut className="h-4 w-4 mr-2" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {!sidebarOpen && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute top-3 left-3 z-10"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </Button>
        )}
        {children}
      </main>
    </div>
  );
}
