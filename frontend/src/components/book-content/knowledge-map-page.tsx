"use client";

/**
 * Knowledge Map — the component behind /knowledge and /knowledge/[...path].
 *
 * Layout (FEATURES.md Task 6.4):
 *   Left panel  40%  → Subject selector + toggle + Outline tree OR KnowledgeGraph
 *   Right panel 60%  → BookContentReader (empty until a node is clicked)
 *
 * The selection IS the URL:
 *   /knowledge/<subject>/<topic>   one topic open
 *   /knowledge/<subject>           a subject, nothing open
 * Written with native history.pushState so the App Router syncs usePathname
 * without a server round-trip and this component stays mounted. The legacy
 * `?topic=&subject=` form is still read (older share links, bookmarks) and
 * is canonicalised to the path form on arrival.
 */

import { Suspense } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { usePathname, useSearchParams } from "next/navigation";

import {
  isUuid,
  knowledgePath,
  segmentMatches,
  type SluggedRef,
} from "@/lib/content-urls";
import {
  ChevronDown,
  ChevronRight,
  BookOpen,
  Loader2,
  PanelLeft,
  PanelLeftClose,
} from "lucide-react";

import { getBookSubjects, getBookTree } from "@/lib/api/book-content";
import { cn } from "@/lib/utils";
import type {
  SubjectWithPlan,
  SubjectTree,
  TreeModule,
  TreeTopic,
} from "@/types/book-content";

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

import BookContentReader, {
  type OverviewChild,
  type OverviewNode,
} from "@/components/book-content/book-content-reader";
import GraphToggleButton, {
  ViewMode,
  VIEW_MODE_KEY,
} from "@/components/book-content/graph-toggle-button";

// ─────────────────────────────────────────────────────────────────────────────
// OVERVIEW NODES  (subject / module — built from the tree already in state)
// ─────────────────────────────────────────────────────────────────────────────

/** Depth-first: every topic under `topics`, including nested subtopics. */
function flattenTopics(
  topics: TreeTopic[],
  acc: TreeTopic[] = [],
): TreeTopic[] {
  for (const t of topics) {
    acc.push(t);
    flattenTopics(t.subtopics, acc);
  }
  return acc;
}

/**
 * "Ready" is `has_content` — a BookContent row exists — never a content_status
 * value (G2.7). The pipeline's `complete` lock state also means an article
 * exists, and 878 topics sat grey in this UI for months because the status
 * string was read instead.
 */
function moduleChild(m: TreeModule): OverviewChild {
  const all = flattenTopics(m.topics);
  return {
    id: m.id,
    name: m.name,
    node_type: "module",
    has_content: all.some((t) => t.has_content),
    content_status: all.some((t) => t.content_status === "generating")
      ? "generating"
      : "empty",
  };
}

function firstReady(topics: TreeTopic[]): OverviewNode["startHere"] {
  const hit = flattenTopics(topics).find((t) => t.has_content);
  return hit ? { id: hit.id, name: hit.name } : null;
}

function countReady(topics: TreeTopic[]): number {
  return topics.filter((t) => t.has_content).length;
}

/**
 * G3.10 — resolve a node in the loaded tree by id, in either direction.
 * The tree is the only place the map knows module and topic slugs, so URL
 * writing (id → slug) and URL reading (slug → id) both go through it.
 */
function findNodeRef(tree: SubjectTree | null, id: string): SluggedRef | null {
  if (!tree) return null;
  if (tree.id === id) return { id: tree.id, slug: tree.slug };
  const mod = tree.modules.find((m) => m.id === id);
  if (mod) return { id: mod.id, slug: mod.slug };
  const topic = tree.modules
    .flatMap((m) => flattenTopics(m.topics))
    .find((t) => t.id === id);
  return topic ? { id: topic.id, slug: topic.slug } : null;
}

function findNodeBySegment(
  tree: SubjectTree | null,
  segment: string,
): SluggedRef | null {
  if (!tree) return null;
  if (segmentMatches(segment, tree)) return { id: tree.id, slug: tree.slug };
  const mod = tree.modules.find((m) => segmentMatches(segment, m));
  if (mod) return { id: mod.id, slug: mod.slug };
  const topic = tree.modules
    .flatMap((m) => flattenTopics(m.topics))
    .find((t) => segmentMatches(segment, t));
  return topic ? { id: topic.id, slug: topic.slug } : null;
}

/**
 * Breadcrumb trail for the reader: Subject › Module › Topic › … › selected.
 * Walks the tree; every crumb is clickable (it is a node id the map can select).
 */
function buildTrail(
  tree: SubjectTree | null,
  id: string | null,
): { id: string; name: string }[] {
  if (!tree || !id) return [];
  const subject = { id: tree.id, name: tree.name };
  if (id === tree.id) return [subject];

  for (const mod of tree.modules) {
    const modCrumb = { id: mod.id, name: mod.name };
    if (mod.id === id) return [subject, modCrumb];
    const path = findPath(mod.topics, id);
    if (path) return [subject, modCrumb, ...path];
  }
  return [];
}

/** Depth-first path of {id,name} from a root topic down to `targetId`. */
function findPath(
  topics: TreeTopic[],
  targetId: string,
): { id: string; name: string }[] | null {
  for (const t of topics) {
    const here = { id: t.id, name: t.name };
    if (t.id === targetId) return [here];
    const below = findPath(t.subtopics, targetId);
    if (below) return [here, ...below];
  }
  return null;
}

/**
 * If `id` names the subject or one of its modules, describe it for the reader.
 * Returns null for topic nodes, which have real articles.
 */
function buildOverview(
  id: string,
  subject: SubjectWithPlan | undefined,
  tree: SubjectTree | null,
): OverviewNode | null {
  if (!tree) return null;

  if (id === tree.id) {
    const all = tree.modules.flatMap((m) => flattenTopics(m.topics));
    return {
      id,
      name: tree.name,
      kind: "subject",
      description: subject?.description || undefined,
      children: tree.modules.map(moduleChild),
      startHere: firstReady(tree.modules.flatMap((m) => m.topics)),
      generatedCount: countReady(all),
      totalCount: all.length,
    };
  }

  const mod = tree.modules.find((m) => m.id === id);
  if (mod) {
    const all = flattenTopics(mod.topics);
    return {
      id,
      name: mod.name,
      kind: "module",
      children: mod.topics.map((t) => ({
        id: t.id,
        name: t.name,
        node_type: t.node_type,
        has_content: t.has_content,
        content_status: t.content_status,
      })),
      startHere: firstReady(mod.topics),
      generatedCount: countReady(all),
      totalCount: all.length,
    };
  }

  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// OUTLINE TREE  (collapsible tree for "outline" mode)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Walk the recursive TreeTopic tree. If targetId is found, push every ancestor's
 * id into `acc` and return true. Used to auto-expand the path to a selected node.
 */
function collectAncestorIds(
  topics: TreeTopic[],
  targetId: string,
  acc: Set<string>,
): boolean {
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

function OutlineNode({
  topic,
  depth,
  onSelect,
  selectedId,
  expandedIds,
}: OutlineNodeProps) {
  const [expanded, setExpanded] = useState(
    () => depth === 0 || expandedIds.has(topic.id),
  );

  // When the selected topic changes (URL nav), auto-expand ancestor nodes
  useEffect(() => {
    if (expandedIds.has(topic.id)) setExpanded(true);
  }, [expandedIds, topic.id]);
  const hasChildren = topic.subtopics.length > 0;
  const isSelected = selectedId === topic.id;

  // Ready is `has_content`; the status string only styles the in-between states.
  const dotClass = topic.has_content
    ? "bg-green-500"
    : topic.content_status === "generating"
      ? "bg-yellow-400 animate-pulse"
      : topic.content_status === "failed"
        ? "bg-red-400"
        : "bg-muted-foreground/30";
  const dotTitle = topic.has_content ? "Article ready" : topic.content_status;

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
          className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", dotClass)}
          title={dotTitle}
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

function KnowledgePageInner() {
  // ── State ────────────────────────────────────────────────────────────────
  const [viewMode, setViewMode] = useState<ViewMode>("outline");
  const [subjects, setSubjects] = useState<SubjectWithPlan[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>("");
  const [tree, setTree] = useState<SubjectTree | null>(null);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [selectedTopicName, setSelectedTopicName] = useState<string>("");

  const [loadingSubjects, setLoadingSubjects] = useState(true);
  const [loadingTree, setLoadingTree] = useState(false);

  // ── Resizable panel split (desktop only) ────────────────────────────────
  const [splitPct, setSplitPct] = useState(38);
  const splitPctRef = useRef(38); // tracks latest value in drag closure
  const isDragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // ── Mobile layout state ──────────────────────────────────────────────────
  const [isMobile, setIsMobile] = useState(false);
  const [showMobilePanel, setShowMobilePanel] = useState(false);

  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Path form first; legacy query form as fallback.
  // /knowledge/<subject>/<topic> → ["knowledge", subject, topic]
  const segments = pathname.split("/").filter(Boolean);
  const subjectParam = segments[1] ?? searchParams.get("subject");
  const topicParam = segments[2] ?? searchParams.get("topic");
  const arrivedViaQuery = segments.length === 1 && searchParams.size > 0;

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

  // ── State → URL ──────────────────────────────────────────────────────────
  // Native pushState, not router.push: the App Router syncs usePathname from
  // it with no server round-trip, and every topic gets a path the
  // route-change tracker and the read beacon can see. State is held in refs
  // so handleNodeSelect keeps a stable identity for the graph.
  //
  // G3.10: the URL is written with SLUGS wherever the loaded data knows them —
  // the subject from the subjects list, the topic/module from the tree — and
  // falls back to the UUID for anything not yet loaded. Both forms resolve.
  const subjectIdRef = useRef("");
  const subjectsRef = useRef<SubjectWithPlan[]>([]);
  const treeRef = useRef<SubjectTree | null>(null);
  useEffect(() => {
    subjectIdRef.current = selectedSubjectId;
  }, [selectedSubjectId]);
  useEffect(() => {
    subjectsRef.current = subjects;
  }, [subjects]);
  useEffect(() => {
    treeRef.current = tree;
  }, [tree]);

  const writeUrl = useCallback(
    (
      topicId: string | null,
      subjectId: string,
      mode: "push" | "replace" = "push",
    ) => {
      const subjectNode =
        subjectsRef.current.find((s) => s.id === subjectId) ?? subjectId;
      const topicNode = topicId
        ? (findNodeRef(treeRef.current, topicId) ?? topicId)
        : null;
      const url = knowledgePath(subjectNode, topicNode);
      if (mode === "replace") window.history.replaceState(null, "", url);
      else window.history.pushState(null, "", url);
    },
    [],
  );

  // ── URL → state ──────────────────────────────────────────────────────────
  // <subject> → switches the left panel; resolved from the subjects list when
  //             it is a slug, used directly when it is a UUID.
  // <topic>   → pre-loads the reader; a slug is resolved against the tree
  //             (subject, module or any topic beneath), a UUID is used directly.
  // Both re-run on Back/Forward (the router re-syncs usePathname on popstate)
  // and when the data they resolve against arrives. An absent topic clears the
  // reader so Back to a subject-only URL matches a fresh load of it.
  useEffect(() => {
    if (!subjectParam) return;
    if (isUuid(subjectParam)) {
      setSelectedSubjectId(subjectParam);
      return;
    }
    const match = subjects.find((s) => segmentMatches(subjectParam, s));
    if (match) setSelectedSubjectId(match.id);
  }, [subjectParam, subjects]);

  useEffect(() => {
    if (!topicParam) {
      setSelectedTopicId(null);
      return;
    }
    if (isUuid(topicParam)) {
      setSelectedTopicId(topicParam);
      return;
    }
    const match = findNodeBySegment(tree, topicParam);
    if (match) setSelectedTopicId(match.id);
  }, [topicParam, tree]);

  // Canonicalise in place: a legacy query-form arrival, or a UUID path that the
  // now-loaded data can express as slugs, is rewritten with replaceState — no
  // history entry, no server round-trip, and the tracker sees the final URL.
  useEffect(() => {
    if (!selectedSubjectId) return;
    const wantsRewrite =
      arrivedViaQuery ||
      (subjectParam && isUuid(subjectParam)) ||
      (topicParam && isUuid(topicParam));
    if (!wantsRewrite) return;
    const subjectKnown = subjects.some((s) => s.id === selectedSubjectId);
    const topicKnown = !selectedTopicId || !!findNodeRef(tree, selectedTopicId);
    if (subjectKnown && topicKnown) {
      writeUrl(selectedTopicId, selectedSubjectId, "replace");
    }
  }, [
    arrivedViaQuery,
    subjectParam,
    topicParam,
    selectedSubjectId,
    selectedTopicId,
    subjects,
    tree,
    writeUrl,
  ]);

  // The tab title follows the selected topic, and PageViewTracker sends it as
  // page_title — GA4 drops the query string from page_path, so the title is
  // what keeps topics apart in its Pages report. Deep-links arrive with no
  // name; BookContentReader fills it in once the article loads.
  useEffect(() => {
    if (selectedTopicId && selectedTopicName) {
      document.title = `${selectedTopicName} — TheKnowledgeOrbits`;
    }
  }, [selectedTopicId, selectedTopicName]);

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
      const rect = containerRef.current.getBoundingClientRect();
      const raw = ((ev.clientX - rect.left) / rect.width) * 100;
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
        localStorage.setItem(
          "tko_panel_split",
          String(Math.round(splitPctRef.current)),
        );
      } catch {
        // ignore
      }
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, []);

  // ── Fetch subjects on mount ───────────────────────────────────────────────
  // A subject in the URL already called setSelectedSubjectId above — don't
  // overwrite it. Fall back to data[0] only if none was encoded, and
  // canonicalise the address bar to it (replace, not push — no bare entry).
  // A legacy `?topic=` with no subject keeps its topic through the rewrite.
  useEffect(() => {
    getBookSubjects()
      .then((data) => {
        setSubjects(data);
        if (data.length > 0 && !subjectParam) {
          setSelectedSubjectId(data[0].id);
          writeUrl(topicParam, data[0].id, "replace");
        }
      })
      .catch(() => {
        /* silently handled below */
      })
      .finally(() => setLoadingSubjects(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Fetch the tree when the subject changes — in BOTH modes ───────────────
  // The outline draws it; the graph does not, but the reader needs it to
  // describe a subject or module node (buildOverview). One cached GET.
  const [treeFailed, setTreeFailed] = useState(false);
  useEffect(() => {
    if (!selectedSubjectId) return;
    setTree(null);
    setTreeFailed(false);
    setLoadingTree(true);
    getBookTree(selectedSubjectId)
      .then(setTree)
      .catch(() => {
        setTree(null);
        setTreeFailed(true);
      })
      .finally(() => setLoadingTree(false));
  }, [selectedSubjectId]);

  // ── Breadcrumb trail for the reader (Subject › Module › … › selected) ─────
  const trail = useMemo(
    () => buildTrail(tree, selectedTopicId),
    [tree, selectedTopicId],
  );

  // ── Overview for subject / module selections (null for topic nodes) ──────
  const overview = useMemo(
    () =>
      selectedTopicId
        ? buildOverview(
            selectedTopicId,
            subjects.find((s) => s.id === selectedSubjectId),
            tree,
          )
        : null,
    [selectedTopicId, selectedSubjectId, subjects, tree],
  );

  // ── Node selection handler (shared by both graph + outline) ───────────────
  const handleNodeSelect = useCallback(
    (topicId: string, topicName: string) => {
      setSelectedTopicId(topicId);
      setSelectedTopicName(topicName);
      writeUrl(topicId, subjectIdRef.current);
      // On mobile: hide the panel so the article fills the screen
      if (typeof window !== "undefined" && window.innerWidth < 768) {
        setShowMobilePanel(false);
      }
    },
    [writeUrl],
  );

  // ── View mode change ──────────────────────────────────────────────────────
  // The tree is loaded per subject regardless of mode, so switching is just state.
  const handleViewModeChange = useCallback((mode: ViewMode) => {
    setViewMode(mode);
  }, []);

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
            {showMobilePanel ? (
              <>
                <PanelLeftClose className="h-3.5 w-3.5" />
                Hide Outline
              </>
            ) : (
              <>
                <PanelLeft className="h-3.5 w-3.5" />
                Browse Topics
              </>
            )}
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
          isMobile ? cn("w-full", showMobilePanel ? "flex-1" : "hidden") : "",
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
                writeUrl(null, e.target.value);
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
            {selectedSubjectId &&
              subjects.length > 0 &&
              (() => {
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

            {!loadingTree &&
              tree &&
              tree.modules.map((mod) => (
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
        {/* topicId is withheld until the tree has arrived (or failed) so a
            subject/module id is never fetched as an article in the gap before
            buildOverview can recognise it. `tree` rather than `loadingTree`:
            the reader's effect runs before this page's on the first commit,
            and loadingTree is still false then. */}
        <BookContentReader
          topicId={tree || treeFailed ? selectedTopicId : null}
          topicName={selectedTopicName}
          onSeeAlsoClick={handleNodeSelect}
          overview={overview}
          trail={trail}
          className="h-full"
        />
      </div>
    </div>
  );
}

// ── useSearchParams() requires a Suspense boundary in Next.js 14+ ──────────
// Wrap KnowledgePageInner so /knowledge stays statically prerendered.
export default function KnowledgeMapPage() {
  return (
    <Suspense>
      <KnowledgePageInner />
    </Suspense>
  );
}
