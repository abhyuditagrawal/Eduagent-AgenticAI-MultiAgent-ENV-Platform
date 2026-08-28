"use client";

import { useSession, signOut } from "next-auth/react";
import { useRouter, usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
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
  Pencil,
  Trash2,
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ThemeToggle } from "@/components/theme-toggle";
import { useChatStore, type Conversation } from "@/stores/chat-store";
import api from "@/lib/api";
import { toast } from "sonner";
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
  // nativeButton={false} because the rendered element is an anchor, not a
  // <button> — an <a href> already carries its own interactive semantics.
  return (
    <Button
      render={<Link href={item.href} />}
      nativeButton={false}
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
  const {
    conversations,
    setConversations,
    setActiveConversation,
    removeConversation,
    updateConversation,
  } = useChatStore();

  const [convToDelete, setConvToDelete] = useState<Conversation | null>(null);
  const [deletingConv, setDeletingConv] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");

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

  // Escape clears renamingId, but the input's blur handler is a closure from the
  // previous render and still sees the old id — without this flag, cancelling
  // would save instead.
  const renameCancelled = useRef(false);

  const commitRename = async () => {
    const id = renamingId;
    if (!id) return;

    if (renameCancelled.current) {
      renameCancelled.current = false;
      setRenamingId(null);
      return;
    }

    const title = renameDraft.trim();
    const original = conversations.find((c) => c.id === id);
    setRenamingId(null);

    // Nothing typed, or unchanged — leave it alone rather than round-tripping.
    if (!title || title === original?.title) return;

    // Optimistic: the list updates immediately and rolls back if the call fails.
    updateConversation(id, { title });
    try {
      await api.patch(`/api/chat/conversations/${id}`, { title });
    } catch {
      updateConversation(id, { title: original?.title ?? null });
      toast.error("Could not rename that chat");
    }
  };

  const handleDeleteConversation = async (conv: Conversation) => {
    setDeletingConv(true);
    try {
      await api.delete(`/api/chat/conversations/${conv.id}`);
      const wasActive = useChatStore.getState().activeConversation?.id === conv.id;
      removeConversation(conv.id);
      setConvToDelete(null);
      toast.success("Chat deleted");
      // The open transcript was just cleared, so land somewhere coherent.
      if (wasActive) router.push("/chat");
    } catch (err: unknown) {
      const detail =
        typeof err === "object" && err !== null && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data
              ?.detail
          : undefined;
      toast.error(detail || "Could not delete that chat");
    } finally {
      setDeletingConv(false);
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
                {conversations.map((conv) => {
                  const isEditing = renamingId === conv.id;
                  return (
                    // Siblings, not nested: a delete button inside the select
                    // button would be a <button> inside a <button>.
                    <div
                      key={conv.id}
                      className="group/conv flex items-center rounded-md hover:bg-accent transition-colors"
                    >
                      {isEditing ? (
                        <input
                          autoFocus
                          value={renameDraft}
                          onChange={(e) => setRenameDraft(e.target.value)}
                          onBlur={commitRename}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              renameCancelled.current = false;
                              commitRename();
                            }
                            if (e.key === "Escape") {
                              renameCancelled.current = true;
                              setRenamingId(null);
                            }
                          }}
                          className="flex-1 min-w-0 bg-transparent px-3 py-2 text-sm outline-none ring-1 ring-ring/40 rounded-md"
                        />
                      ) : (
                        <>
                          <button
                            onClick={() => handleSelectConversation(conv)}
                            className="flex-1 min-w-0 text-left px-3 py-2 text-sm truncate"
                            title={conv.title || "New conversation"}
                          >
                            <MessageSquare className="h-3.5 w-3.5 inline mr-2 opacity-60" />
                            {conv.title || "New conversation"}
                          </button>
                          <button
                            onClick={() => {
                              renameCancelled.current = false;
                              setRenamingId(conv.id);
                              setRenameDraft(conv.title || "");
                            }}
                            title="Rename"
                            aria-label={`Rename ${conv.title || "conversation"}`}
                            className="shrink-0 p-1.5 rounded opacity-0 group-hover/conv:opacity-60 hover:!opacity-100 focus-visible:opacity-100"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => setConvToDelete(conv)}
                            title="Delete"
                            aria-label={`Delete ${conv.title || "conversation"}`}
                            className="shrink-0 p-1.5 mr-1 rounded opacity-0 group-hover/conv:opacity-60 hover:!opacity-100 hover:text-destructive focus-visible:opacity-100"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  );
                })}
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

      <Dialog
        open={convToDelete !== null}
        onOpenChange={(open) => {
          if (!open && !deletingConv) setConvToDelete(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this chat?</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              &ldquo;{convToDelete?.title || "New conversation"}&rdquo; and all of
              its messages will be removed. Your mastery scores and progress stay
              as they are. This cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                disabled={deletingConv}
                onClick={() => setConvToDelete(null)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={deletingConv}
                onClick={() =>
                  convToDelete && handleDeleteConversation(convToDelete)
                }
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete chat
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
