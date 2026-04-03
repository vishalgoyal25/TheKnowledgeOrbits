"use client";

/**
 * /knowledge — Knowledge Map page.
 *
 * Layout (FEATURES.md Task 6.4):
 *   Left panel  40%  → Subject selector + toggle + Outline tree OR KnowledgeGraph
 *   Right panel 60%  → BookContentReader (empty until a node is clicked)
 *
 * This is a NEW standalone page. No existing page is modified.
 * "Knowledge Map" nav link is added in Task 6.5 (header.tsx).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { ChevronDown, ChevronRight, BookOpen, Loader2, PanelLeft, PanelLeftClose } from "lucide-react";

import { getBookSubjects, getBookTree } from "@/lib/api/book-content";
import { cn } from "@/lib/utils";
import type { SubjectWithPlan, SubjectTree, TreeTopic } from "@/types/book-content";

/**
 * D3.js is a heavy 500KB+ library.
 * Dynamic import with ssr:false keeps it OUT of the server bundle, which:
 *   - Eliminates the OOM crash on first cold-start compile
 *   - Cuts first compile from ~100s to ~5s
 *   - Stops ETIMEDOUT errors (SSR no longer tries to call book APIs server-side)
 */
const KnowledgeGraph = dynamic(
  () => import("@/components/book-content/knowledge-graph"),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-full gap-2 text-muted-foreground text-sm">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading graph engine…
      </div>
    ),
  },
);

import BookContentReader from "@/components/book-content/book-content-reader";
import GraphToggleButton, {
  ViewMode,
  VIEW_MODE_KEY,
} from "@/components/book-content/graph-toggle-button";

// ─────────────────────────────────────────────────────────────────────────────
// OUTLINE TREE  (collapsible tree for "outline" mode)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Walk the recursive TreeTopic tree. If targetId is found, push every ancestor's
 * id into `acc` and return true. Used to auto-expand the path to a selected node.
 */
function collectAncestorIds(topics: TreeTopic[], targetId: string, acc: Set<string>): boolean {
  for (const t of topics) {
    if (t.id === targetId) return true;
    if (collectAncestorIds(t.subtopics, targetId, acc)) {
      acc.add(t.id);
      return true;
    }
  }
  return false;
}

interface OutlineNodeProps {
  topic: TreeTopic;
  depth: number;
  onSelect: (id: string, name: string) => void;
  selectedId: string | null;
  /** IDs of all ancestors of the currently selected topic — forces expansion */
  expandedIds: Set<string>;
}

function OutlineNode({ topic, depth, onSelect, selectedId, expandedIds }: OutlineNodeProps) {
  const [expanded, setExpanded] = useState(() => depth === 0 || expandedIds.has(topic.id));

  // When the selected topic changes (URL nav), auto-expand ancestor nodes
  useEffect(() => {
    if (expandedIds.has(topic.id)) setExpanded(true);
  }, [expandedIds, topic.id]);
  const hasChildren = topic.subtopics.length > 0;
  const isSelected = selectedId === topic.id;

  const statusDot: Record<string, string> = {
    book_quality: "bg-green-500",
    generating:   "bg-yellow-400 animate-pulse",
    failed:       "bg-red-400",
    empty:        "bg-muted-foreground/30",
  };

  return (
    <div>
      <div
        className={cn(
          "flex items-center gap-1.5 px-2 py-1.5 rounded-md cursor-pointer select-none transition-colors text-sm group",
          isSelected
            ? "bg-primary/10 text-primary font-medium"
            : "hover:bg-muted/60 text-foreground/80",
        )}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        onClick={() => {
          if (hasChildren) setExpanded((e) => !e);
          onSelect(topic.id, topic.name);
        }}
      >
        {/* Expand / collapse chevron */}
        {hasChildren ? (
          expanded ? (
            <ChevronDown className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
          )
        ) : (
          <span className="w-3 flex-shrink-0" />
        )}

        {/* Content-status dot */}
        <span
          className={cn(
            "w-1.5 h-1.5 rounded-full flex-shrink-0",
            statusDot[topic.content_status] ?? statusDot.empty,
          )}
          title={topic.content_status}
        />

        {/* Name */}
        <span className="truncate flex-1">{topic.name}</span>

        {/* Child count badge */}
        {hasChildren && (
          <span className="text-[10px] text-muted-foreground/60 ml-auto flex-shrink-0">
            {topic.subtopics.length}
          </span>
        )}
      </div>

      {/* Children */}
      {hasChildren && expanded && (
        <div>
          {topic.subtopics.map((child) => (
            <OutlineNode
              key={child.id}
              topic={child}
              depth={depth + 1}
              onSelect={onSelect}
              selectedId={selectedId}
              expandedIds={expandedIds}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN PAGE
// ─────────────────────────────────────────────────────────────────────────────

export default function KnowledgePage() {
  // ── State ────────────────────────────────────────────────────────────────
  const [viewMode, setViewMode]           = useState<ViewMode>("outline");
  const [subjects, setSubjects]           = useState<SubjectWithPlan[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>("");
  const [tree, setTree]                   = useState<SubjectTree | null>(null);
  const [selectedTopicId, setSelectedTopicId]     = useState<string | null>(null);
  const [selectedTopicName, setSelectedTopicName] = useState<string>("");

  const [loadingSubjects, setLoadingSubjects] = useState(true);
  const [loadingTree, setLoadingTree]         = useState(false);

  // ── Resizable panel split (desktop only) ────────────────────────────────
  const [splitPct, setSplitPct]   = useState(38);
  const splitPctRef               = useRef(38);   // tracks latest value in drag closure
  const isDragging                = useRef(false);
  const containerRef              = useRef<HTMLDivElement>(null);

  // ── Mobile layout state ──────────────────────────────────────────────────
  const [isMobile, setIsMobile]             = useState(false);
  const [showMobilePanel, setShowMobilePanel] = useState(false);

  const searchParams = useSearchParams();

  // ── Ancestor IDs for auto-expanding the outline path to the selected topic ─
  const expandedIds = useMemo((): Set<string> => {
    if (!tree || !selectedTopicId) return new Set();
    const acc = new Set<string>();
    for (const mod of tree.modules) {
      for (const topic of mod.topics) {
        if (collectAncestorIds([topic], selectedTopicId, acc)) break;
      }
    }
    return acc;
  }, [tree, selectedTopicId]);

  // ── Pre-select topic + subject from URL query params ─────────────────────
  // ?topic=<uuid>   → pre-loads the article in the right panel
  // ?subject=<uuid> → immediately switches the left panel to the correct subject
  //                   (encoded by hamburger/navbar so no extra API call is needed)
  useEffect(() => {
    const topicParam   = searchParams.get("topic");
    const subjectParam = searchParams.get("subject");
    if (topicParam)   setSelectedTopicId(topicParam);
    if (subjectParam) setSelectedSubjectId(subjectParam);
  }, [searchParams]);

  // ── Restore persisted view mode + panel split from localStorage ─────────
  useEffect(() => {
    try {
      const saved = localStorage.getItem(VIEW_MODE_KEY) as ViewMode | null;
      if (saved === "outline" || saved === "graph") setViewMode(saved);
    } catch {
      // ignore
    }
    try {
      const saved = parseFloat(localStorage.getItem("tko_panel_split") ?? "");
      if (!isNaN(saved) && saved >= 20 && saved <= 78) {
        setSplitPct(saved);
        splitPctRef.current = saved;
      }
    } catch {
      // ignore
    }
  }, []);

  // ── Detect mobile and listen for resize ──────────────────────────────────
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // ── Drag-divider handler ──────────────────────────────────────────────────
  const handleDividerMouseDown = useCallback((e: React.MouseEvent) => {
    // Ignore on mobile — vertical stack layout handles small screens
    if (window.innerWidth < 768) return;
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const onMouseMove = (ev: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect    = containerRef.current.getBoundingClientRect();
      const raw     = ((ev.clientX - rect.left) / rect.width) * 100;
      const clamped = Math.min(78, Math.max(20, raw));
      splitPctRef.current = clamped;
      setSplitPct(clamped);
    };

    const onMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      try {
        localStorage.setItem("tko_panel_split", String(Math.round(splitPctRef.current)));
      } catch {
        // ignore
      }
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, []);

  // ── Fetch subjects on mount ───────────────────────────────────────────────
  // ?subject in URL already called setSelectedSubjectId above — don't overwrite it.
  // Fall back to data[0] only if no subject was encoded in the URL.
  useEffect(() => {
    const subjectParam = searchParams.get("subject");
    getBookSubjects()
      .then((data) => {
        setSubjects(data);
        if (data.length > 0 && !subjectParam) {
          setSelectedSubjectId(data[0].id);
        }
      })
      .catch(() => {/* silently handled below */})
      .finally(() => setLoadingSubjects(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Fetch outline tree when subject changes (outline mode only) ───────────
  useEffect(() => {
    if (!selectedSubjectId || viewMode !== "outline") return;
    setTree(null);
    setLoadingTree(true);
    getBookTree(selectedSubjectId)
      .then(setTree)
      .catch(() => setTree(null))
      .finally(() => setLoadingTree(false));
  }, [selectedSubjectId, viewMode]);

  // ── Node selection handler (shared by both graph + outline) ───────────────
  const handleNodeSelect = useCallback((topicId: string, topicName: string) => {
    setSelectedTopicId(topicId);
    setSelectedTopicName(topicName);
    // On mobile: hide the panel so the article fills the screen
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setShowMobilePanel(false);
    }
  }, []);

  // ── View mode change ──────────────────────────────────────────────────────
  const handleViewModeChange = useCallback((mode: ViewMode) => {
    setViewMode(mode);
    // Load tree on first switch to outline
    if (mode === "outline" && selectedSubjectId && !tree) {
      setLoadingTree(true);
      getBookTree(selectedSubjectId)
        .then(setTree)
        .catch(() => setTree(null))
        .finally(() => setLoadingTree(false));
    }
  }, [selectedSubjectId, tree]);

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div
      ref={containerRef}
      className={cn(
        "overflow-hidden bg-background",
        isMobile
          ? "flex flex-col h-[calc(100vh-64px)]"
          : "flex flex-row h-[calc(100vh-64px)]",
      )}
    >
      {/* ── MOBILE TOGGLE BAR ─────────────────────────────────────────────── */}
      {isMobile && (
        <div className="flex-shrink-0 flex items-center gap-2 px-3 py-2 border-b border-border bg-muted/30">
          <button
            onClick={() => setShowMobilePanel((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
          >
            {showMobilePanel
              ? <><PanelLeftClose className="h-3.5 w-3.5" />Hide Outline</>
              : <><PanelLeft className="h-3.5 w-3.5" />Browse Topics</>
            }
          </button>
          {selectedTopicName && (
            <span className="text-xs text-muted-foreground truncate flex-1 text-right">
              {selectedTopicName}
            </span>
          )}
        </div>
      )}

      {/* ── LEFT PANEL ────────────────────────────────────────────────────── */}
      {/* Desktop: always visible, resizable. Mobile: toggled via showMobilePanel */}
      <div
        className={cn(
          "flex flex-col overflow-hidden flex-shrink-0",
          isMobile
            ? cn("w-full", showMobilePanel ? "flex-1" : "hidden")
            : "",
        )}
        style={!isMobile ? { width: `${splitPct}%` } : undefined}
      >

        {/* Header bar: subject selector + toggle */}
        <div className="flex-shrink-0 px-4 py-3 border-b border-border bg-muted/20 space-y-3">

          {/* Page title */}
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary" />
            <h1 className="text-sm font-bold tracking-wide text-foreground">
              Knowledge Map
            </h1>
          </div>

          {/* Subject selector */}
          {loadingSubjects ? (
            <div className="h-9 rounded-md bg-muted animate-pulse" />
          ) : (
            <select
              value={selectedSubjectId}
              onChange={(e) => {
                setSelectedSubjectId(e.target.value);
                setTree(null);
                setSelectedTopicId(null);
              }}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 transition"
            >
              {subjects.length === 0 && (
                <option value="">No subjects available</option>
              )}
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.book_plan.topics_completed > 0
                    ? ` (${s.book_plan.topics_completed}/${s.book_plan.topics_planned})`
                    : ""}
                </option>
              ))}
            </select>
          )}

          {/* Toggle button */}
          <div className="flex items-center justify-between">
            <GraphToggleButton
              mode={viewMode}
              onChange={handleViewModeChange}
            />
            {/* Progress hint */}
            {selectedSubjectId && subjects.length > 0 && (() => {
              const subj = subjects.find((s) => s.id === selectedSubjectId);
              const pct = subj?.book_plan.completion_pct ?? 0;
              return pct > 0 ? (
                <span className="text-xs text-muted-foreground">
                  {typeof pct === "number" ? pct.toFixed(0) : pct}% generated
                </span>
              ) : null;
            })()}
          </div>
        </div>

        {/* ── OUTLINE MODE ─────────────────────────────────────────────────── */}
        {viewMode === "outline" && (
          <div className="flex-1 overflow-y-auto py-2 [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-thumb]:rounded [&::-webkit-scrollbar-thumb]:bg-border">
            {loadingTree && (
              <div className="flex items-center justify-center py-12 gap-2 text-muted-foreground text-sm">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading outline…
              </div>
            )}

            {!loadingTree && !tree && selectedSubjectId && (
              <div className="py-12 text-center text-sm text-muted-foreground">
                Could not load outline. Try another subject.
              </div>
            )}

            {!loadingTree && tree && tree.modules.map((mod) => (
              <div key={mod.id} className="mb-1">
                {/* Module header */}
                <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-widest text-muted-foreground/60">
                  {mod.name}
                </div>
                {/* Topics */}
                {mod.topics.map((topic) => (
                  <OutlineNode
                    key={topic.id}
                    topic={topic}
                    depth={0}
                    onSelect={handleNodeSelect}
                    selectedId={selectedTopicId}
                    expandedIds={expandedIds}
                  />
                ))}
              </div>
            ))}

            {!loadingTree && tree && tree.modules.length === 0 && (
              <div className="py-12 text-center text-sm text-muted-foreground">
                No topics found for this subject.
              </div>
            )}
          </div>
        )}

        {/* ── GRAPH MODE ───────────────────────────────────────────────────── */}
        {viewMode === "graph" && (
          <div className="flex-1 overflow-hidden">
            {selectedSubjectId ? (
              <KnowledgeGraph
                subjectId={selectedSubjectId}
                onNodeSelect={handleNodeSelect}
                selectedTopicId={selectedTopicId}
                containerVisible={!isMobile || showMobilePanel}
                className="h-full rounded-none border-none"
              />
            ) : (
              <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
                Select a subject to load the graph.
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── DRAG DIVIDER (desktop only) ───────────────────────────────────── */}
      {!isMobile && (
        <div
          onMouseDown={handleDividerMouseDown}
          className="w-1 flex-shrink-0 bg-border hover:bg-primary/40 active:bg-primary/60 cursor-col-resize transition-colors group relative"
          title="Drag to resize"
        >
          {/* Wider invisible hit-area so the divider is easy to grab */}
          <div className="absolute inset-y-0 -left-1.5 -right-1.5" />
        </div>
      )}

      {/* ── RIGHT PANEL ───────────────────────────────────────────────────── */}
      {/* Desktop: remaining width. Mobile: full height when panel hidden, shrinks when panel visible */}
      <div
        className={cn(
          "overflow-hidden p-4",
          isMobile
            ? cn("flex-1 w-full", showMobilePanel ? "hidden" : "block")
            : "flex-1",
        )}
      >
        <BookContentReader
          topicId={selectedTopicId}
          topicName={selectedTopicName}
          onSeeAlsoClick={handleNodeSelect}
          className="h-full"
        />
      </div>
    </div>
  );
}
