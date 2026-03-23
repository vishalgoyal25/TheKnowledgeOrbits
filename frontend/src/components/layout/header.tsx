/**
 * Enhanced header with search bar
 */

"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect, useMemo, useRef } from "react";
import { cn } from "@/lib/utils";
import {
  Search,
  Newspaper,
  ChevronDown,
  BookOpen,
  FileText,
  Folder,
  Sparkles,
  Menu,
  X,
  ChevronRight,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth/useAuth";
import UserMenu from "@/components/auth/UserMenu";
import { useSearch } from "@/lib/hooks/use-search";
import { SearchResult } from "@/lib/api/search";
import { subjectsAPI } from "@/lib/api/subjects";

interface TopicData {
  id: string;
  name: string;
  sub_topics?: { id: string; name: string }[];
}

interface ModuleData {
  id: string;
  name: string;
  topics?: TopicData[];
}

interface SubjectData {
  id: string;
  name: string;
  modules: ModuleData[];
  description?: string;
}

const NEWS_SUBJECT: SubjectData = {
  id: "news",
  name: "News",
  description: "Global news updates and current affairs categorized by theme.",
  modules: [
    {
      id: "news-world",
      name: "World",
      topics: [
        { id: "news-un", name: "United Nations" },
        { id: "news-global-economy", name: "Global Economy" },
      ],
    },
    {
      id: "news-politics",
      name: "Politics",
      topics: [
        { id: "news-elections", name: "Elections" },
        { id: "news-policy", name: "Policy Updates" },
      ],
    },
    {
      id: "news-climate",
      name: "Climate Crisis",
      topics: [
        { id: "news-cop28", name: "COP28" },
        { id: "news-emissions", name: "Carbon Emissions" },
      ],
    },
    {
      id: "news-middle-east",
      name: "Middle East",
      topics: [
        { id: "news-peace", name: "Peace Process" },
        { id: "news-oil", name: "Energy Market" },
      ],
    },
    {
      id: "news-science",
      name: "Science",
      topics: [
        { id: "news-space", name: "Space Exploration" },
        { id: "news-bio", name: "Biotech" },
      ],
    },
    {
      id: "news-tech",
      name: "Tech",
      topics: [
        { id: "news-ai", name: "Artificial Intelligence" },
        { id: "news-chips", name: "Semiconductors" },
      ],
    },
    {
      id: "news-business",
      name: "Business",
      topics: [
        { id: "news-markets", name: "Stock Markets" },
        { id: "news-trade", name: "World Trade" },
      ],
    },
  ],
};

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [isMobileSearchOpen, setIsMobileSearchOpen] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Dynamic Content Hierarchy State
  const [hierarchyData, setHierarchyData] = useState<SubjectData[]>([]);
  const [hoveredSubject, setHoveredSubject] = useState<string | null>(null);
  const [hoveredModuleId, setHoveredModuleId] = useState<string | null>(null);
  const [dropdownPos, setDropdownPos] = useState<{
    left: number;
    top: number;
  } | null>(null);
  const [hoveredModuleTopics, setHoveredModuleTopics] = useState<
    { id: string; name: string; sub_topics?: { id: string; name: string }[] }[]
  >([]);
  // Sub-topic flyout state
  const [hoveredTopicSubtopics, setHoveredTopicSubtopics] = useState<
    { id: string; name: string }[]
  >([]);
  const [subtopicPos, setSubtopicPos] = useState<{
    left: number;
    top: number;
  } | null>(null);

  // Timer ref to delay closing dropdowns (prevents flicker when moving mouse from button to panel)
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const closeAllDropdowns = () => {
    setHoveredModuleId(null);
    setDropdownPos(null);
    setHoveredTopicSubtopics([]);
    setSubtopicPos(null);
  };

  const startCloseTimer = () => {
    closeTimerRef.current = setTimeout(closeAllDropdowns, 200);
  };

  const cancelCloseTimer = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  // Drawer-specific state for the Explorer
  const [drawerActiveSubjectId, setDrawerActiveSubjectId] = useState<
    string | null
  >(null);
  const [drawerActiveModuleId, setDrawerActiveModuleId] = useState<
    string | null
  >(null);

  const currentSubjectId = useMemo(() => {
    if (!hierarchyData || hierarchyData.length === 0) return null;
    const directSubject = hierarchyData.find(
      (s: SubjectData) =>
        pathname.includes(`/subjects/${s.id}`) || pathname.includes(`/news`),
    );
    if (directSubject) return directSubject.id;
    for (const subject of hierarchyData) {
      if (
        subject.modules?.some((m: ModuleData) =>
          pathname.includes(`/modules/${m.id}`),
        )
      ) {
        return subject.id;
      }
    }
    return hierarchyData[0].id;
  }, [pathname, hierarchyData]);

  const displaySubjectId = hoveredSubject || currentSubjectId;

  useEffect(() => {
    const fetchHierarchy = async () => {
      try {
        const data = await subjectsAPI.getHierarchy();
        if (data && data.length > 0) {
          const backendSubjects = data[0].subjects || [];
          setHierarchyData([NEWS_SUBJECT, ...backendSubjects]);
        } else {
          setHierarchyData([NEWS_SUBJECT]);
        }
      } catch (err) {
        console.error("Failed to fetch dynamic hierarchy:", err);
      }
    };
    fetchHierarchy();
  }, []);

  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const { data: searchResults, isLoading: isSearching } = useSearch(
    { q: debouncedQuery, limit: 10 },
    debouncedQuery.length >= 2,
  );

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      setIsFocused(false);
      setIsMobileSearchOpen(false);
      setIsDrawerOpen(false);
      router.push(`/search?q=${encodeURIComponent(searchQuery)}`);
    }
  };

  // ── FEATURE 1: Close drawer on back/forward browser navigation ──────────
  useEffect(() => {
    setIsDrawerOpen(false);
  }, [pathname]);

  // ── FEATURE 2: Pre-select active Subject/Module from URL when drawer opens ─
  useEffect(() => {
    if (!isDrawerOpen || hierarchyData.length === 0) return;

    // Find active subject from current URL
    let activeSubject: string | null = null;
    let activeModule: string | null = null;

    for (const subject of hierarchyData) {
      if (
        pathname.includes(`/subjects/${subject.id}`) ||
        (subject.id === "news" && pathname.includes("/current-affairs"))
      ) {
        activeSubject = subject.id;
        break;
      }
      const matchedModule = subject.modules?.find((m) =>
        pathname.includes(`/modules/${m.id}`),
      );
      if (matchedModule) {
        activeSubject = subject.id;
        activeModule = matchedModule.id;
        break;
      }
      const matchedTopic = subject.modules?.find(
        (m) => m.topics?.some((t) => pathname.includes(`/topics/${t.id}`)),
      );
      if (matchedTopic) {
        activeSubject = subject.id;
        activeModule = matchedTopic.id;
        break;
      }
    }

    setDrawerActiveSubjectId(activeSubject ?? hierarchyData[0]?.id ?? null);
    setDrawerActiveModuleId(activeModule);
  }, [isDrawerOpen, pathname, hierarchyData]);

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/60">
      {/* MOBILE SEARCH OVERLAY (Only visible when toggled on mobile) */}
      {isMobileSearchOpen && (
        <div className="md:hidden absolute inset-0 bg-white z-[60] flex items-center px-4 animate-in slide-in-from-top duration-300">
          <form
            onSubmit={handleSearchSubmit}
            className="flex-1 relative flex items-center"
          >
            <Search className="absolute left-3 h-4 w-4 text-slate-400" />
            <Input
              autoFocus
              className="pl-10 pr-10 h-11 bg-slate-50 border-none focus:ring-0"
              placeholder="Search orbits..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button
              type="button"
              onClick={() => setIsMobileSearchOpen(false)}
              className="absolute right-3 p-1 text-slate-400 hover:text-slate-900"
            >
              <X className="h-5 w-5" />
            </button>
          </form>
        </div>
      )}

      {/* LAYER 1: TOP BAR (Brand, Search, Utility) */}
      <div className="border-b bg-white/50 relative z-50">
        <div className="container mx-auto px-4">
          <div className="flex h-16 items-center justify-between gap-4">
            {/* Hamburger + Logo Group */}
            <div className="flex items-center gap-2 md:gap-4 shrink-0">
              {/* SYLLABUS EXPLORER HAMBURGER */}
              <Sheet open={isDrawerOpen} onOpenChange={setIsDrawerOpen}>
                <SheetTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="shrink-0 -ml-2 hover:bg-slate-100"
                  >
                    <Menu className="h-6 w-6 text-slate-700" />
                  </Button>
                </SheetTrigger>
                <SheetContent
                  side="left"
                  className="w-full sm:max-w-2xl p-0 flex flex-col overflow-hidden"
                >
                  {/* ── FEATURE 3: Staggered slide-in header ─────────── */}
                  <SheetHeader className="p-6 border-b bg-slate-50 animate-in slide-in-from-left duration-300">
                    <SheetTitle className="flex items-center gap-3">
                      <BookOpen className="h-6 w-6 text-blue-600" />
                      <span className="font-black tracking-tight text-xl uppercase">
                        Syllabus Explorer
                      </span>
                    </SheetTitle>
                  </SheetHeader>

                  {/* EXPLORER MATRIX — each column animates in with stagger */}
                  <div className="flex-1 flex overflow-hidden">
                    {/* COL 1: SUBJECTS + DRAWER SEARCH — slides in first */}
                    <div className="w-[140px] sm:w-[180px] border-r overflow-y-auto no-scrollbar bg-slate-50/50 flex flex-col animate-in slide-in-from-left duration-300 delay-75">
                      {/* BBC-STYLE DRAWER SEARCH BAR */}
                      <div className="p-4 border-b bg-white relative">
                        <form
                          onSubmit={handleSearchSubmit}
                          className="relative group/drawer-search"
                        >
                          <Input
                            type="search"
                            placeholder="Search news, topics and more"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onFocus={() => setIsFocused(true)}
                            onBlur={() =>
                              setTimeout(() => setIsFocused(false), 200)
                            }
                            className="pr-10 h-10 bg-slate-100 border-none focus:bg-white focus:ring-1 focus:ring-slate-300 transition-all rounded-sm text-sm"
                          />
                          <button
                            type="submit"
                            className="absolute right-0 top-0 h-full w-10 flex items-center justify-center bg-slate-800 text-white hover:bg-slate-900 transition-colors rounded-sm"
                          >
                            <Search className="h-4 w-4" />
                          </button>
                        </form>

                        {/* DRAWER SMART DROPDOWN RESULTS */}
                        {isFocused && searchQuery.length >= 2 && (
                          <div className="absolute top-full left-4 right-4 mt-1 bg-white rounded-md shadow-2xl border border-slate-200 overflow-hidden max-h-[60vh] overflow-y-auto z-[100] animate-in fade-in slide-in-from-top-1">
                            {isSearching ? (
                              <div className="p-4 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                                <Sparkles className="h-4 w-4 animate-spin text-blue-500" />{" "}
                                Thinking...
                              </div>
                            ) : searchResults && searchResults.length > 0 ? (
                              <div className="py-2">
                                {searchResults.map((result: SearchResult) => (
                                  <Link
                                    key={result.id}
                                    href={result.url || "#"}
                                    onMouseDown={(e) => {
                                      e.preventDefault();
                                      setIsFocused(false);
                                      setIsDrawerOpen(false);
                                      setSearchQuery("");
                                      router.push(result.url || "#");
                                    }}
                                    className="block px-4 py-3 hover:bg-slate-50 transition-colors border-b border-slate-50"
                                  >
                                    <div className="flex items-start gap-3">
                                      <div
                                        className={cn(
                                          "h-7 w-7 rounded flex items-center justify-center shrink-0 mt-0.5 text-white",
                                          result.type === "topic"
                                            ? "bg-purple-500"
                                            : result.type === "current_affair"
                                              ? "bg-emerald-500"
                                              : "bg-blue-500",
                                        )}
                                      >
                                        {result.type === "topic" ? (
                                          <Folder className="h-3.5 w-3.5" />
                                        ) : result.type === "current_affair" ? (
                                          <Newspaper className="h-3.5 w-3.5" />
                                        ) : (
                                          <FileText className="h-3.5 w-3.5" />
                                        )}
                                      </div>
                                      <div>
                                        <h4 className="text-[13px] font-bold text-slate-900 line-clamp-1 leading-tight">
                                          {result.title}
                                        </h4>
                                        <p className="text-[10px] text-slate-500 line-clamp-1 mt-0.5">
                                          {result.snippet}
                                        </p>
                                      </div>
                                    </div>
                                  </Link>
                                ))}
                                <button
                                  onMouseDown={(e) => {
                                    e.preventDefault();
                                    setIsFocused(false);
                                    setIsDrawerOpen(false);
                                    router.push(
                                      `/search?q=${encodeURIComponent(
                                        searchQuery,
                                      )}`,
                                    );
                                  }}
                                  className="block w-full py-2 text-center text-xs font-bold text-blue-600 bg-blue-50/50 hover:bg-blue-100 transition-colors"
                                >
                                  View all results
                                </button>
                              </div>
                            ) : (
                              <div className="p-4 text-center">
                                <p className="text-slate-500 text-xs">
                                  No results found.
                                </p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="p-3 space-y-1">
                        <div className="px-3 py-2 text-[10px] font-black text-slate-400 uppercase tracking-widest">
                          Global Map
                        </div>
                        <Link
                          href="/"
                          onClick={() => setIsDrawerOpen(false)}
                          className={cn(
                            "flex items-center px-3 py-2.5 text-sm font-bold rounded-lg transition-all",
                            pathname === "/"
                              ? "bg-blue-50 text-blue-600"
                              : "text-slate-600 hover:bg-white",
                          )}
                        >
                          Home
                        </Link>
                        <Link
                          href="/about"
                          onClick={() => setIsDrawerOpen(false)}
                          className={cn(
                            "flex items-center px-3 py-2.5 text-sm font-bold rounded-lg transition-all",
                            pathname === "/about"
                              ? "bg-blue-50 text-blue-600"
                              : "text-slate-600 hover:bg-white",
                          )}
                        >
                          About
                        </Link>
                        <Link
                          href="/contact"
                          onClick={() => setIsDrawerOpen(false)}
                          className={cn(
                            "flex items-center px-3 py-2.5 text-sm font-bold rounded-lg transition-all",
                            pathname === "/contact"
                              ? "bg-blue-50 text-blue-600"
                              : "text-slate-600 hover:bg-white",
                          )}
                        >
                          Contact Us
                        </Link>

                        <div className="mt-6 px-3 py-2 text-[10px] font-black text-slate-400 uppercase tracking-widest">
                          Core Subjects
                        </div>
                        {hierarchyData.map((s) => {
                          const isCurrentSubject =
                            drawerActiveSubjectId === s.id;
                          return (
                            <button
                              key={s.id}
                              onMouseEnter={() =>
                                setDrawerActiveSubjectId(s.id)
                              }
                              onClick={() => {
                                setDrawerActiveSubjectId(s.id);
                                setDrawerActiveModuleId(null);
                              }}
                              className={cn(
                                "w-full flex items-center justify-between px-3 py-2.5 text-sm font-bold rounded-lg transition-all text-left",
                                isCurrentSubject
                                  ? "bg-blue-600 text-white shadow-md shadow-blue-200"
                                  : "text-slate-600 hover:bg-white/50",
                              )}
                            >
                              <span>{s.name}</span>
                              <ChevronRight
                                className={cn(
                                  "h-4 w-4 transition-transform duration-200",
                                  isCurrentSubject
                                    ? "opacity-100 translate-x-0.5"
                                    : "opacity-40",
                                )}
                              />
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* COL 2: MODULES — slides in second with a slightly longer delay */}
                    <div
                      className={cn(
                        "w-[140px] sm:w-[180px] border-r overflow-y-auto no-scrollbar animate-in slide-in-from-left duration-300 delay-150",
                        !drawerActiveSubjectId && "bg-slate-50/20",
                      )}
                    >
                      {drawerActiveSubjectId ? (
                        <div className="p-3 space-y-1">
                          <div className="px-3 py-2 text-[10px] font-black text-blue-400 uppercase tracking-widest">
                            Modules
                          </div>
                          {hierarchyData
                            .find((s) => s.id === drawerActiveSubjectId)
                            ?.modules?.map((m) => {
                              const isCurrentModule =
                                drawerActiveModuleId === m.id;
                              return (
                                <button
                                  key={m.id}
                                  onMouseEnter={() =>
                                    setDrawerActiveModuleId(m.id)
                                  }
                                  onClick={() => setDrawerActiveModuleId(m.id)}
                                  className={cn(
                                    "w-full flex items-center justify-between px-3 py-2.5 text-sm font-bold rounded-lg transition-all text-left",
                                    isCurrentModule
                                      ? "bg-slate-800 text-white shadow-sm"
                                      : "text-slate-600 hover:bg-slate-50",
                                  )}
                                >
                                  <span className="leading-snug">{m.name}</span>
                                  <ChevronRight
                                    className={cn(
                                      "h-4 w-4 transition-transform duration-200 shrink-0",
                                      isCurrentModule
                                        ? "opacity-100 translate-x-0.5"
                                        : "opacity-40",
                                    )}
                                  />
                                </button>
                              );
                            })}
                        </div>
                      ) : (
                        <div className="h-full flex items-center justify-center p-8 text-center">
                          <p className="text-xs text-slate-400 font-medium italic">
                            Hover a subject to explore modules
                          </p>
                        </div>
                      )}
                    </div>

                    {/* COL 3: TOPICS — slides in last with the longest delay */}
                    <div className="flex-1 min-w-0 overflow-y-auto no-scrollbar bg-white animate-in slide-in-from-left duration-300 delay-200">
                      {drawerActiveModuleId ? (
                        <div className="p-4 space-y-1">
                          <div className="px-3 py-2 text-[10px] font-black text-emerald-500 uppercase tracking-widest">
                            Syllabus Topics
                          </div>
                          {(() => {
                            const activeModule = hierarchyData
                              .find((s) => s.id === drawerActiveSubjectId)
                              ?.modules?.find(
                                (m) => m.id === drawerActiveModuleId,
                              );
                            const isNewsModule =
                              drawerActiveSubjectId === "news";

                            const flatTopics: {
                              id: string;
                              name: string;
                              isSubTopic?: boolean;
                            }[] = [];
                            const seenIds = new Set<string>();

                            activeModule?.topics?.forEach((t) => {
                              if (!seenIds.has(t.id)) {
                                flatTopics.push({ id: t.id, name: t.name });
                                seenIds.add(t.id);
                              }
                              t.sub_topics?.forEach((st) => {
                                if (!seenIds.has(st.id)) {
                                  flatTopics.push({
                                    id: st.id,
                                    name: st.name,
                                    isSubTopic: true,
                                  });
                                  seenIds.add(st.id);
                                }
                              });
                            });

                            return flatTopics.map((t, i) => {
                              const isActiveTopic = pathname.includes(
                                `/topics/${t.id}`,
                              );
                              const href = isNewsModule
                                ? "/current-affairs"
                                : `/topics/${t.id}/articles`;
                              return (
                                <Link
                                  key={`drawer-topic-${t.id}`}
                                  href={href}
                                  onClick={() => setIsDrawerOpen(false)}
                                  style={{ animationDelay: `${i * 20}ms` }}
                                  className={cn(
                                    "block rounded-lg transition-all border-l-2 animate-in fade-in slide-in-from-right-2 duration-200",
                                    t.isSubTopic
                                      ? "px-5 py-2 text-[11px] font-medium"
                                      : "px-3 py-2.5 text-xs font-bold",
                                    isActiveTopic
                                      ? "bg-emerald-50 text-emerald-700 border-emerald-500"
                                      : "text-slate-700 hover:bg-emerald-50 hover:text-emerald-700 border-transparent hover:border-emerald-400",
                                  )}
                                >
                                  {t.name}
                                </Link>
                              );
                            });
                          })()}
                        </div>
                      ) : (
                        <div className="h-full flex items-center justify-center p-8 text-center">
                          <FileText
                            className="h-12 w-12 text-slate-100 mb-2 mx-auto"
                            strokeWidth={1}
                          />
                          <p className="text-xs text-slate-400 font-medium italic px-4">
                            Select a module to jump directly to topics
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </SheetContent>
              </Sheet>

              {/* Logo */}
              <Link href="/" className="flex items-center space-x-2 shrink-0">
                <BookOpen className="h-7 w-7 text-blue-600" />
                <div className="flex flex-col">
                  <span className="text-base sm:text-xl font-black text-slate-900 tracking-tight leading-none">
                    TheKnowledgeOrbits
                  </span>
                  <span className="hidden sm:inline-block text-[10px] font-bold text-blue-600 uppercase tracking-widest mt-1">
                    AI-Powered UPSC OS
                  </span>
                </div>
              </Link>
            </div>

            {/* Central Search Bar - (DESKTOP / LANDSCAPE) */}
            <div className="hidden md:block flex-1 max-w-xl relative">
              <form onSubmit={handleSearchSubmit} className="relative group">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 group-focus-within:text-blue-600 transition-colors pointer-events-none" />
                <Input
                  type="search"
                  placeholder="Ask anything about UPSC Syllabus..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setTimeout(() => setIsFocused(false), 200)}
                  className="pl-10 pr-4 h-11 bg-slate-50 border-slate-200 focus:bg-white focus:ring-2 focus:ring-blue-100 transition-all rounded-xl w-full"
                />
              </form>

              {/* SMART DROPDOWN RESULTS */}
              {isFocused && searchQuery.length >= 2 && (
                <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-2xl shadow-xl border border-slate-100 overflow-hidden max-h-[80vh] overflow-y-auto z-[70] animate-in fade-in slide-in-from-top-2">
                  {isSearching ? (
                    <div className="p-4 text-center text-sm text-slate-500 flex items-center justify-center gap-2">
                      <Sparkles className="h-4 w-4 animate-spin text-blue-500" />{" "}
                      Thinking...
                    </div>
                  ) : searchResults && searchResults.length > 0 ? (
                    <div className="py-2">
                      {searchResults.map((result: SearchResult) => (
                        <Link
                          key={result.id}
                          href={result.url || "#"}
                          onMouseDown={(e) => {
                            // FAST NAVIGATION: Capture before onBlur hides the dropdown
                            e.preventDefault();
                            setIsFocused(false);
                            setSearchQuery("");
                            router.push(result.url || "#");
                          }}
                          className="block px-4 py-3 hover:bg-slate-50 transition-colors"
                        >
                          <div className="flex items-start gap-3">
                            <div
                              className={cn(
                                "h-8 w-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5",
                                result.type === "topic"
                                  ? "bg-purple-100 text-purple-600"
                                  : result.type === "current_affair"
                                    ? "bg-emerald-100 text-emerald-600"
                                    : "bg-blue-100 text-blue-600",
                              )}
                            >
                              {result.type === "topic" ? (
                                <Folder className="h-4 w-4" />
                              ) : result.type === "current_affair" ? (
                                <Newspaper className="h-4 w-4" />
                              ) : (
                                <FileText className="h-4 w-4" />
                              )}
                            </div>
                            <div>
                              <h4 className="text-sm font-bold text-slate-900 line-clamp-1">
                                {result.title}
                              </h4>
                              <p className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
                                {result.snippet}
                              </p>
                            </div>
                          </div>
                        </Link>
                      ))}
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            {/* Top Right Utility */}
            <div className="flex items-center gap-2 sm:gap-6">
              <nav className="hidden xl:flex items-center gap-6 text-sm font-semibold text-slate-600">
                <Link
                  href="/"
                  className="hover:text-blue-600 transition-colors"
                >
                  Home
                </Link>
                <Link
                  href="/about"
                  className="hover:text-blue-600 transition-colors"
                >
                  About
                </Link>
                <Link
                  href="/contact"
                  className="hover:text-blue-600 transition-colors"
                >
                  Contact Us
                </Link>
              </nav>

              {/* MOBILE SEARCH TRIGGER */}
              <Button
                variant="ghost"
                size="icon"
                className="md:hidden text-slate-600"
                onClick={() => setIsMobileSearchOpen(true)}
              >
                <Search className="h-5 w-5" />
              </Button>

              <div className="flex items-center space-x-2 sm:border-l pl-0 sm:pl-6 border-slate-200 h-8">
                {!isLoading &&
                  (isAuthenticated ? (
                    <UserMenu />
                  ) : (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        asChild
                        className="hidden lg:inline-flex font-bold"
                      >
                        <Link href="/auth/login">Login</Link>
                      </Button>
                      <Button
                        size="sm"
                        asChild
                        className="bg-blue-600 hover:bg-blue-700 font-bold shadow-md shadow-blue-200 whitespace-nowrap"
                      >
                        <Link href="/auth/register">Join Pro</Link>
                      </Button>
                    </>
                  ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* TIER 1: SUBJECTS (Horizontal Ribbon) */}
      <div
        className="bg-white border-b relative z-40 shadow-sm overflow-hidden"
        onMouseLeave={() => setHoveredSubject(null)}
      >
        <div className="container mx-auto px-4">
          <nav className="flex items-center h-12 overflow-x-auto no-scrollbar scroll-smooth">
            {hierarchyData.map((subject) => {
              const isActive = displaySubjectId === subject.id;
              const isNews = subject.id === "news";
              return (
                <Link
                  key={subject.id}
                  href={isNews ? "/current-affairs" : `/subjects/${subject.id}`}
                  className={cn(
                    "flex items-center px-5 h-full text-sm font-bold transition-all whitespace-nowrap shrink-0 border-b-2 border-r border-slate-200 group",
                    isActive
                      ? isNews
                        ? "text-red-600 border-b-red-600 bg-red-50/50"
                        : "text-blue-700 border-b-blue-700 bg-blue-50/50"
                      : "text-slate-600 border-b-transparent hover:text-slate-900 hover:bg-slate-50",
                  )}
                  onMouseEnter={() => setHoveredSubject(subject.id)}
                >
                  {subject.name}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* TIER 2: MODULES (Swipable Ribbon) */}
        {displaySubjectId && (
          <div
            className="bg-slate-50 shadow-inner border-b relative z-30 block"
            onMouseLeave={startCloseTimer}
          >
            <div className="container mx-auto px-4">
              <nav className="flex items-center h-9 overflow-x-auto overflow-y-visible no-scrollbar scroll-smooth w-full relative z-[100]">
                {hierarchyData
                  .find((s) => s.id === displaySubjectId)
                  ?.modules?.map((module: ModuleData) => {
                    const isActiveModule = pathname.includes(
                      `/modules/${module.id}`,
                    );
                    const isHovered = hoveredModuleId === module.id;
                    const allTopics: { id: string; name: string }[] = [];
                    module.topics?.forEach((t) => {
                      allTopics.push({ id: t.id, name: t.name });
                      t.sub_topics?.forEach((st) =>
                        allTopics.push({ id: st.id, name: st.name }),
                      );
                    });
                    const hasTopics = allTopics.length > 0;

                    return (
                      <div
                        key={module.id}
                        className="h-full shrink-0 flex items-center border-r border-slate-300 relative group/module"
                        onMouseEnter={(e) => {
                          const rect = (
                            e.currentTarget as HTMLElement
                          ).getBoundingClientRect();
                          setDropdownPos({ left: rect.left, top: rect.bottom });
                          const topics =
                            module.topics?.map((t) => ({
                              id: t.id,
                              name: t.name,
                              sub_topics: t.sub_topics || [],
                            })) || [];
                          setHoveredModuleTopics(topics);
                          setHoveredModuleId(module.id);
                          // clear sub-topic flyout
                          setHoveredTopicSubtopics([]);
                          setSubtopicPos(null);
                        }}
                      >
                        <Link
                          href={`/modules/${module.id}`}
                          className={cn(
                            "flex items-center px-4 h-full text-[11px] font-extrabold uppercase tracking-widest transition-all whitespace-nowrap",
                            isActiveModule || isHovered
                              ? "text-blue-600 bg-white"
                              : "text-slate-500 hover:text-slate-900",
                          )}
                        >
                          {module.name}
                          {hasTopics && (
                            <ChevronDown
                              className={cn(
                                "ml-1 h-3 w-3 opacity-50 transition-transform duration-300",
                                isHovered &&
                                  "rotate-180 opacity-100 text-blue-600",
                              )}
                            />
                          )}
                        </Link>
                      </div>
                    );
                  })}
              </nav>
            </div>
          </div>
        )}

        {/* FIXED-POSITION TOPIC DROPDOWN — breaks out of overflow:auto nav, overlays entire page */}
        {hoveredModuleId && dropdownPos && hoveredModuleTopics.length > 0 && (
          <div
            className="fixed z-[99999] w-[260px] bg-white border border-slate-200 shadow-2xl rounded-b-md"
            style={{ left: dropdownPos.left, top: dropdownPos.top }}
            onMouseEnter={cancelCloseTimer}
            onMouseLeave={startCloseTimer}
          >
            <div className="max-h-[60vh] overflow-y-auto no-scrollbar py-1">
              {hoveredModuleTopics.map((topic) => {
                const hasSubs = (topic.sub_topics?.length ?? 0) > 0;
                return (
                  <div
                    key={`fixed-topic-${topic.id}`}
                    className="relative flex items-center justify-between group/topicrow"
                    onMouseEnter={(e) => {
                      if (hasSubs) {
                        const rect = (
                          e.currentTarget as HTMLElement
                        ).getBoundingClientRect();
                        setSubtopicPos({ left: rect.right, top: rect.top });
                        setHoveredTopicSubtopics(topic.sub_topics || []);
                      } else {
                        setHoveredTopicSubtopics([]);
                        setSubtopicPos(null);
                      }
                    }}
                  >
                    <Link
                      href={`/topics/${topic.id}/articles`}
                      onClick={() => {
                        setHoveredModuleId(null);
                        setDropdownPos(null);
                        setHoveredTopicSubtopics([]);
                        setSubtopicPos(null);
                      }}
                      className="flex-1 block px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100 hover:text-blue-600 transition-colors"
                    >
                      {topic.name}
                    </Link>
                    {hasSubs && (
                      <span className="pr-3 text-slate-500 group-hover/topicrow:text-blue-600 text-[12px] font-bold">
                        ›
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* FIXED-POSITION SUB-TOPIC PANEL — opens horizontally to the right of a hovered topic */}
        {subtopicPos && hoveredTopicSubtopics.length > 0 && hoveredModuleId && (
          <div
            className="fixed z-[99999] w-[240px] bg-white border border-slate-200 shadow-2xl rounded-md"
            style={{ left: subtopicPos.left, top: subtopicPos.top }}
            onMouseEnter={cancelCloseTimer}
            onMouseLeave={startCloseTimer}
          >
            <div className="max-h-[50vh] overflow-y-auto no-scrollbar py-1">
              {hoveredTopicSubtopics.map((st) => (
                <Link
                  key={`fixed-sub-${st.id}`}
                  href={`/topics/${st.id}/articles`}
                  onClick={() => {
                    setHoveredModuleId(null);
                    setDropdownPos(null);
                    setHoveredTopicSubtopics([]);
                    setSubtopicPos(null);
                  }}
                  className="block px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 hover:text-blue-600 transition-colors"
                >
                  {st.name}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
