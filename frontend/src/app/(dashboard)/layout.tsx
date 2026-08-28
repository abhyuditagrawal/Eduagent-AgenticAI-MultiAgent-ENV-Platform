"use client";

import { useSession, signOut } from "next-auth/react";
import { useRouter, usePathname } from "next/navigation";
import { useCallback, useEffect } from "react";
import Link from "next/link";
import {
  MessageSquare,
  Plus,
  Upload,
  LogOut,
  GraduationCap,
  PanelLeftOpen,
  PanelLeftClose,
  ChevronDown,
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
  type LucideIcon,
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
import { usePersistedState } from "@/lib/use-persisted-state";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

interface NavSection {
  id: string;
  label: string;
  items: NavItem[];
}

/** Nav is data, not markup — sections can be reordered or extended in one place. */
const NAV_SECTIONS: NavSection[] = [
  {
    id: "learn",
    label: "Learn",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/my-subjects", label: "My Subjects", icon: BookOpen },
      { href: "/flashcards", label: "Flashcards", icon: Brain },
    ],
  },
  {
    id: "explore",
    label: "Explore",
    items: [
      { href: "/concept-map", label: "Concept Map", icon: Network },
      { href: "/knowledge-frontier", label: "Knowledge Frontier", icon: Compass },
      { href: "/knowledge-tracing", label: "Knowledge Tracing", icon: Activity },
      { href: "/learning-path", label: "Learning Path", icon: TrendingUp },
    ],
  },
  {
    id: "practice",
    label: "Practice",
    items: [
      { href: "/debate", label: "Debate Arena", icon: Swords },
      { href: "/study-planner", label: "Study Planner", icon: CalendarDays },
      { href: "/study-groups", label: "Study Groups", icon: Users },
      { href: "/learning-genome", label: "Learning Genome", icon: Dna },
    ],
  },
];

const ADMIN_ITEMS: NavItem[] = [
  { href: "/admin/upload", label: "Upload PDFs", icon: Upload },
  { href: "/admin/subjects", label: "Manage Subjects", icon: BookOpen },
  { href: "/admin/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/admin/custom-agents", label: "Custom Agents", icon: Bot },
];

const SIDEBAR_KEY = "eduagent.sidebar.open";
const SECTIONS_KEY = "eduagent.sidebar.sections";
const NO_SECTIONS: string[] = [];
const PROFILE_ITEM: NavItem = { href: "/profile", label: "Profile", icon: User };

/** One nav row, rendered as a full button or an icon-only rail button. */
function NavLink({
  item,
  expanded,
  active,
}: {
  item: NavItem;
  expanded: boolean;
  active: boolean;
}) {
  const Icon = item.icon;
  // `render` composes into a single <a>. Nesting <Button> inside <Link> would
  // put a <button> inside an <a>, which is invalid HTML.
  return (
    <Button
      render={<Link href={item.href} />}
      title={expanded ? undefined : item.label}
      variant={active ? "secondary" : "ghost"}
      className={
        expanded
          ? "w-full justify-start gap-2 text-sm"
          : "w-full justify-center px-0"
      }
      size={expanded ? "default" : "icon"}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {expanded && <span className="truncate">{item.label}</span>}
    </Button>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session, status } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, persistSidebar] = usePersistedState(SIDEBAR_KEY, true);
  const [collapsedSections, setCollapsedSections] = usePersistedState<string[]>(
    SECTIONS_KEY,
    NO_SECTIONS
  );
  const { conversations, setConversations, setActiveConversation } =
    useChatStore();

  const toggleSection = (id: string) => {
    setCollapsedSections(
      collapsedSections.includes(id)
        ? collapsedSections.filter((s) => s !== id)
        : [...collapsedSections, id]
    );
  };

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    }
  }, [status, router]);

  const loadConversations = useCallback(async () => {
    try {
      const res = await api.get("/api/chat/history");
      setConversations(res.data);
    } catch {
      // Silently fail on initial load
    }
  }, [setConversations]);

  useEffect(() => {
    if (session?.accessToken) {
      loadConversations();
    }
  }, [session?.accessToken, loadConversations]);

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

  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar — expands to a full panel, collapses to an icon rail */}
      <aside
        className={`${
          sidebarOpen ? "w-72" : "w-16"
        } transition-[width] duration-300 bg-card border-r flex flex-col overflow-hidden shrink-0`}
      >
        {/* Header */}
        <div className="p-3 flex items-center gap-2 shrink-0">
          {sidebarOpen ? (
            <>
              <GraduationCap className="h-6 w-6 text-primary shrink-0" />
              <span className="font-bold text-lg whitespace-nowrap">
                EduAgent
              </span>
              <div className="ml-auto flex items-center gap-0.5 shrink-0">
                <ThemeToggle />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => persistSidebar(false)}
                  title="Collapse sidebar"
                >
                  <PanelLeftClose className="h-4 w-4" />
                </Button>
              </div>
            </>
          ) : (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 mx-auto"
              onClick={() => persistSidebar(true)}
              title="Expand sidebar"
            >
              <PanelLeftOpen className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* New chat */}
        <div className={`${sidebarOpen ? "px-3" : "px-2"} pb-2 shrink-0`}>
          <Button
            className={
              sidebarOpen
                ? "w-full justify-start gap-2"
                : "w-full justify-center px-0"
            }
            size={sidebarOpen ? "default" : "icon"}
            onClick={handleNewChat}
            title={sidebarOpen ? undefined : "New Chat"}
          >
            <Plus className="h-4 w-4 shrink-0" />
            {sidebarOpen && "New Chat"}
          </Button>
        </div>

        {/* Nav + conversations share one scroll region so the footer stays pinned */}
        <ScrollArea className="flex-1 min-h-0">
          <div className={`${sidebarOpen ? "px-3" : "px-2"} pb-2 space-y-2`}>
            {NAV_SECTIONS.map((section) => {
              const collapsed = collapsedSections.includes(section.id);
              return (
                <div key={section.id} className="space-y-1">
                  {sidebarOpen && (
                    <button
                      onClick={() => toggleSection(section.id)}
                      className="w-full flex items-center gap-1 px-3 pt-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <ChevronDown
                        className={`h-3 w-3 transition-transform ${
                          collapsed ? "-rotate-90" : ""
                        }`}
                      />
                      {section.label}
                    </button>
                  )}
                  {(!collapsed || !sidebarOpen) &&
                    section.items.map((item) => (
                      <NavLink
                        key={item.href}
                        item={item}
                        expanded={sidebarOpen}
                        active={isActive(item.href)}
                      />
                    ))}
                </div>
              );
            })}

            {session?.user?.role === "admin" && (
              <div className="space-y-1">
                {sidebarOpen && (
                  <button
                    onClick={() => toggleSection("admin")}
                    className="w-full flex items-center gap-1 px-3 pt-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <ChevronDown
                      className={`h-3 w-3 transition-transform ${
                        collapsedSections.includes("admin") ? "-rotate-90" : ""
                      }`}
                    />
                    Admin
                  </button>
                )}
                {(!collapsedSections.includes("admin") || !sidebarOpen) &&
                  ADMIN_ITEMS.map((item) => (
                    <NavLink
                        key={item.href}
                        item={item}
                        expanded={sidebarOpen}
                        active={isActive(item.href)}
                      />
                  ))}
              </div>
            )}

            {sidebarOpen && conversations.length > 0 && (
              <div className="space-y-1">
                <Separator className="my-2" />
                <p className="px-3 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Recent
                </p>
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
            )}
          </div>
        </ScrollArea>

        <Separator />

        {/* Footer — always visible */}
        <div className={`${sidebarOpen ? "p-3" : "p-2"} space-y-1 shrink-0`}>
          <NavLink
            item={PROFILE_ITEM}
            expanded={sidebarOpen}
            active={isActive(PROFILE_ITEM.href)}
          />

          {!sidebarOpen && (
            <div className="flex justify-center py-1">
              <ThemeToggle />
            </div>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger
              className={`w-full flex items-center gap-2 text-sm rounded-md hover:bg-accent transition-colors ${
                sidebarOpen ? "px-3 py-2" : "justify-center py-2"
              }`}
              title={sidebarOpen ? undefined : session?.user?.name || "Account"}
            >
              <Avatar className="h-6 w-6 shrink-0">
                <AvatarFallback className="text-xs">{initials}</AvatarFallback>
              </Avatar>
              {sidebarOpen && (
                <span className="truncate">{session?.user?.name}</span>
              )}
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
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {children}
      </main>
    </div>
  );
}
