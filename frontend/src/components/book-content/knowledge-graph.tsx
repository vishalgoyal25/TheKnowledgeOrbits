"use client";

/**
 * KnowledgeGraph — D3.js force-directed graph for the Book Content Engine.
 *
 * Ported from: upsc-agent-lab/src/templates/index.html (vis-network POC)
 * Rewritten in:  D3.js v7 + React 19 (as specified in FEATURES.md Task 6.2)
 *
 * Behaviours (from FEATURES.md spec):
 *   - Progressive disclosure: initially shows only root/module nodes
 *   - Single click collapsed node  → fetch children → animate into view
 *   - Single click expanded node   → collapse all descendants
 *   - Single click leaf node       → fire onNodeSelect (open article reader)
 *   - Double click any node        → fire onNodeSelect (open article reader)
 *   - Drag nodes to reposition     (D3 drag, re-anchors on release)
 *   - Scroll / pinch to zoom       (D3 zoom, scale 0.2 – 4×)
 *
 * Node visual types (FEATURES.md):
 *   subject_root  → large  orange  #f97316
 *   module        → medium blue    #3b82f6
 *   topic         → small  green   #22c55e
 *   subtopic      → tiny   grey    #6b7280
 *   sub_subtopic  → tiny   grey    #9ca3af
 *
 * Edge types:
 *   contains  → solid grey line
 *   semantic  → dashed orange line (related_to / cross_subject / etc.)
 */

import { useCallback, useEffect, useRef, useState } from "react";
import * as d3 from "d3";

import { getBookGraph } from "@/lib/api/book-content";
import { cn } from "@/lib/utils";
import type { GraphData, TopicNode } from "@/types/book-content";

// ─────────────────────────────────────────────────────────────────────────────
// VISUAL CONFIG  (ported from POC TYPE_COLORS / TYPE_SIZE)
// ─────────────────────────────────────────────────────────────────────────────

const NODE_CONFIG: Record<string, { color: string; size: number }> = {
  subject_root: { color: "#f97316", size: 34 },
  module: { color: "#3b82f6", size: 26 },
  topic: { color: "#22c55e", size: 20 },
  subtopic: { color: "#6b7280", size: 14 },
  sub_subtopic: { color: "#9ca3af", size: 10 },
};

const LEGEND_ITEMS = [
  { label: "Subject", color: "#f97316" },
  { label: "Module", color: "#3b82f6" },
  { label: "Topic", color: "#22c55e" },
  { label: "Subtopic", color: "#6b7280" },
];

// ─────────────────────────────────────────────────────────────────────────────
// D3 SIMULATION TYPES
// ─────────────────────────────────────────────────────────────────────────────

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  name: string;
  node_type: string;
  content_status: string;
  parent_topic_id: string | null;
  quality_score: number | null;
  /** Number of direct children in the full graph */
  childCount: number;
}

interface SimEdge extends d3.SimulationLinkDatum<SimNode> {
  edgeType: "contains" | "semantic";
  relation_type?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// PROPS
// ─────────────────────────────────────────────────────────────────────────────

interface KnowledgeGraphProps {
  /** UUID of the subject to render */
  subjectId: string;
  /** Called when a leaf node or double-clicked node should open the article reader */
  onNodeSelect: (topicId: string, topicName: string) => void;
  /** UUID of the currently selected topic — highlights that node and auto-expands its ancestor chain */
  selectedTopicId?: string | null;
  /**
   * Pass false when the graph container is hidden (e.g. mobile panel collapsed).
   * When it transitions true → visible, the graph re-reads real dimensions and redraws.
   * Defaults to true (always visible on desktop).
   */
  containerVisible?: boolean;
  className?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────

function buildChildCountMap(data: GraphData): Map<string, number> {
  const map = new Map<string, number>();
  for (const edge of data.edges.hierarchical) {
    map.set(edge.source, (map.get(edge.source) ?? 0) + 1);
  }
  return map;
}

function getDescendantIds(nodeId: string, data: GraphData): Set<string> {
  const result = new Set<string>();
  const queue = [nodeId];
  while (queue.length > 0) {
    const cur = queue.shift()!;
    for (const e of data.edges.hierarchical) {
      if (e.source === cur && !result.has(e.target)) {
        result.add(e.target);
        queue.push(e.target);
      }
    }
  }
  return result;
}

function truncate(text: string, maxLen = 22): string {
  return text.length > maxLen ? text.slice(0, maxLen) + "…" : text;
}

function nodeLabel(node: SimNode, expanded: Set<string>): string {
  const name = truncate(node.name);
  if (node.childCount > 0) {
    const arrow = expanded.has(node.id) ? "▼" : "▶";
    return `${name} ${arrow} (${node.childCount})`;
  }
  return name;
}

// ─────────────────────────────────────────────────────────────────────────────
// COMPONENT
// ─────────────────────────────────────────────────────────────────────────────

export default function KnowledgeGraph({
  subjectId,
  onNodeSelect,
  selectedTopicId,
  containerVisible = true,
  className,
}: KnowledgeGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const simulationRef = useRef<d3.Simulation<SimNode, SimEdge> | null>(null);
  const graphDataRef = useRef<GraphData | null>(null);
  const expandedRef = useRef<Set<string>>(new Set());
  const selectedTopicIdRef = useRef<string | null>(null);
  // Click-delay timer: holds single-click 250ms so dblclick can cancel it
  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Preserve zoom/pan across topology rebuilds (node expand/collapse)
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const lastZoomTransformRef = useRef<d3.ZoomTransform>(d3.zoomIdentity);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [visibleNodeIds, setVisibleNodeIds] = useState<Set<string>>(new Set());
  const [stats, setStats] = useState({ nodes: 0, edges: 0 });

  // ── Fetch full graph on subject change ────────────────────────────────────
  useEffect(() => {
    if (!subjectId) return;

    setLoading(true);
    setError(null);
    expandedRef.current = new Set();
    graphDataRef.current = null;
    setVisibleNodeIds(new Set());

    getBookGraph(subjectId)
      .then((data) => {
        graphDataRef.current = data;

        // Initial visibility: subject_root only → true progressive disclosure
        // User clicks subject → modules appear → click module → topics appear
        const initial = new Set(
          data.nodes
            .filter((n) => n.node_type === "subject_root")
            .map((n) => n.id),
        );
        // Fallback 1: no subject_root → show modules
        if (initial.size === 0) {
          data.nodes
            .filter((n) => n.node_type === "module")
            .forEach((n) => initial.add(n.id));
        }
        // Fallback 2: no modules either → show root-level topics (no parent)
        if (initial.size === 0) {
          data.nodes
            .filter((n) => n.parent_topic_id === null)
            .forEach((n) => initial.add(n.id));
        }

        setVisibleNodeIds(initial);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load knowledge graph. Please try again.");
        setLoading(false);
      });

    return () => {
      simulationRef.current?.stop();
    };
  }, [subjectId]);

  // ── Auto-expand ancestor chain when selectedTopicId is set (URL nav) ───────
  // Runs when: graph data finishes loading (loading → false) OR selectedTopicId changes.
  // Builds parent-lookup from hierarchical edges, walks up to subject_root,
  // makes the full chain + their direct siblings visible, marks ancestors expanded.
  useEffect(() => {
    selectedTopicIdRef.current = selectedTopicId ?? null;

    const data = graphDataRef.current;
    if (loading || !selectedTopicId || !data) return;

    // Build child→parent lookup
    const parentMap = new Map<string, string>();
    for (const e of data.edges.hierarchical) {
      parentMap.set(e.target, e.source);
    }

    // Walk from selectedTopicId up to subject_root
    const chain = new Set<string>([selectedTopicId]);
    let cur = selectedTopicId;
    while (parentMap.has(cur)) {
      cur = parentMap.get(cur)!;
      chain.add(cur);
      expandedRef.current.add(cur);
    }

    // Make all chain nodes + their direct children visible
    setVisibleNodeIds((prev) => {
      const next = new Set(prev);
      chain.forEach((id) => next.add(id));
      // Also reveal direct children of each ancestor so the path looks natural
      for (const id of chain) {
        data.edges.hierarchical
          .filter((e) => e.source === id)
          .forEach((e) => next.add(e.target));
      }
      return next;
    });

    // Apply highlight immediately on the existing SVG (no simulation restart)
    const svg = svgRef.current;
    if (svg) {
      d3.select(svg)
        .selectAll<SVGCircleElement, SimNode>("circle.main-circle")
        .attr("stroke-width", (d) => (d.id === selectedTopicId ? 4 : 2))
        .attr("stroke", (d) =>
          d.id === selectedTopicId
            ? "#ffffff"
            : (NODE_CONFIG[d.node_type] ?? NODE_CONFIG.subtopic).color,
        );
    }
  }, [selectedTopicId, loading]);

  // ── Click handler: expand / collapse / select ─────────────────────────────
  const handleNodeClick = useCallback(
    (nodeId: string) => {
      const data = graphDataRef.current;
      if (!data) return;

      const node = data.nodes.find((n) => n.id === nodeId);
      if (!node) return;

      const childCountMap = buildChildCountMap(data);
      const childCount = childCountMap.get(nodeId) ?? 0;
      const isLeaf = childCount === 0;

      if (isLeaf) {
        // Leaf → open article reader
        onNodeSelect(nodeId, node.name);
        return;
      }

      if (expandedRef.current.has(nodeId)) {
        // Collapse: remove all descendants from visible set
        const descendants = getDescendantIds(nodeId, data);
        expandedRef.current.delete(nodeId);
        descendants.forEach((id) => expandedRef.current.delete(id));

        setVisibleNodeIds((prev) => {
          const next = new Set(prev);
          descendants.forEach((id) => next.delete(id));
          return next;
        });
      } else {
        // Expand: add only direct children
        expandedRef.current.add(nodeId);
        const directChildren = data.edges.hierarchical
          .filter((e) => e.source === nodeId)
          .map((e) => e.target);

        setVisibleNodeIds((prev) => {
          const next = new Set(prev);
          directChildren.forEach((id) => next.add(id));
          return next;
        });
      }
    },
    [onNodeSelect],
  );

  // ── Double-click: always open article reader ──────────────────────────────
  const handleNodeDblClick = useCallback(
    (nodeId: string) => {
      const data = graphDataRef.current;
      if (!data) return;
      const node = data.nodes.find((n) => n.id === nodeId);
      if (node) onNodeSelect(nodeId, node.name);
    },
    [onNodeSelect],
  );

  // ── D3 render: runs whenever visible node set changes ────────────────────
  useEffect(() => {
    const data = graphDataRef.current;
    const svg = svgRef.current;
    if (!data || !svg || visibleNodeIds.size === 0 || loading) return;

    // Stop any running simulation
    simulationRef.current?.stop();

    const childCountMap = buildChildCountMap(data);

    // Filter nodes + edges to currently visible set
    const simNodes: SimNode[] = data.nodes
      .filter((n) => visibleNodeIds.has(n.id))
      .map((n: TopicNode) => ({
        ...n,
        childCount: childCountMap.get(n.id) ?? 0,
      }));

    const visibleSet = new Set(simNodes.map((n) => n.id));

    const simEdges: SimEdge[] = [
      ...data.edges.hierarchical
        .filter((e) => visibleSet.has(e.source) && visibleSet.has(e.target))
        .map((e) => ({
          source: e.source,
          target: e.target,
          edgeType: "contains" as const,
        })),
      ...data.edges.semantic
        .filter(
          (e) =>
            visibleSet.has(e.source_topic_id) &&
            visibleSet.has(e.target_topic_id),
        )
        .map((e) => ({
          source: e.source_topic_id,
          target: e.target_topic_id,
          edgeType: "semantic" as const,
          relation_type: e.relation_type,
        })),
    ];

    setStats({ nodes: simNodes.length, edges: simEdges.length });

    // Use wrapper div dimensions — more reliable than getBoundingClientRect()
    // on SVG which can return 0×0 before browser layout completes.
    const wrapper = wrapperRef.current;
    const W = wrapper?.clientWidth || svg.clientWidth || 700;
    const H = wrapper?.clientHeight || svg.clientHeight || 500;

    // ── Preserve zoom/pan before clearing SVG ────────────────────────────────
    // Saves current transform so we can restore it after rebuild.
    // Prevents zoom/pan resetting when user expands/collapses a node.
    if (zoomRef.current) {
      lastZoomTransformRef.current = d3.zoomTransform(svg);
    }

    // ── Clear & rebuild SVG ─────────────────────────────────────────────────
    const root = d3.select(svg);
    root.selectAll("*").remove();

    // Zoomable group
    const g = root.append("g");
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.15, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
        lastZoomTransformRef.current = event.transform;
      });
    root.call(zoom);
    zoomRef.current = zoom;
    // Disable D3 zoom's built-in dblclick-to-zoom — it intercepts node dblclick
    root.on("dblclick.zoom", null);

    // Restore previous zoom/pan — preserves user's view across node expand/collapse
    // Skip on first render (zoomIdentity = no transform applied yet)
    if (lastZoomTransformRef.current !== d3.zoomIdentity) {
      root.call(zoom.transform, lastZoomTransformRef.current);
    }

    // Arrow markers for edge ends
    const defs = root.append("defs");

    const makeArrow = (id: string, color: string) =>
      defs
        .append("marker")
        .attr("id", id)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 22)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("fill", color);

    makeArrow("arrow-contains", "#4b5563");
    makeArrow("arrow-semantic", "#f97316");

    // ── Edges ───────────────────────────────────────────────────────────────
    const edgeGroup = g.append("g").attr("class", "edges");

    const edgeSel = edgeGroup
      .selectAll<SVGLineElement, SimEdge>("line")
      .data(simEdges)
      .join("line")
      .attr("stroke", (d) =>
        d.edgeType === "semantic" ? "#f9731655" : "#4b556335",
      )
      .attr("stroke-width", (d) => (d.edgeType === "semantic" ? 1.5 : 1))
      .attr("stroke-dasharray", (d) =>
        d.edgeType === "semantic" ? "5,4" : "none",
      )
      .attr("marker-end", (d) =>
        d.edgeType === "semantic"
          ? "url(#arrow-semantic)"
          : "url(#arrow-contains)",
      );

    // ── Nodes ───────────────────────────────────────────────────────────────
    const nodeGroup = g.append("g").attr("class", "nodes");

    const nodeSel = nodeGroup
      .selectAll<SVGGElement, SimNode>("g.node")
      .data(simNodes, (d) => d.id)
      .join("g")
      .attr("class", "node")
      .style("cursor", "pointer");

    // Outer glow ring — shown only for book_quality content
    nodeSel
      .filter((d) => d.content_status === "book_quality")
      .append("circle")
      .attr(
        "r",
        (d) => (NODE_CONFIG[d.node_type] ?? NODE_CONFIG.subtopic).size + 5,
      )
      .attr("fill", "none")
      .attr(
        "stroke",
        (d) => (NODE_CONFIG[d.node_type] ?? NODE_CONFIG.subtopic).color,
      )
      .attr("stroke-width", 1)
      .attr("opacity", 0.35);

    // Main circle
    nodeSel
      .append("circle")
      .attr("class", "main-circle")
      .attr("r", (d) => (NODE_CONFIG[d.node_type] ?? NODE_CONFIG.subtopic).size)
      .attr(
        "fill",
        (d) => (NODE_CONFIG[d.node_type] ?? NODE_CONFIG.subtopic).color + "28",
      )
      .attr("stroke", (d) =>
        d.id === selectedTopicIdRef.current
          ? "#ffffff"
          : (NODE_CONFIG[d.node_type] ?? NODE_CONFIG.subtopic).color,
      )
      .attr("stroke-width", (d) =>
        d.id === selectedTopicIdRef.current ? 4 : 2,
      );

    // Label below node
    nodeSel
      .append("text")
      .attr("text-anchor", "middle")
      .attr(
        "dy",
        (d) => (NODE_CONFIG[d.node_type] ?? NODE_CONFIG.subtopic).size + 15,
      )
      .attr("font-size", (d) => {
        const sizes: Record<string, number> = {
          subject_root: 13,
          module: 12,
          topic: 11,
          subtopic: 10,
          sub_subtopic: 9,
        };
        return sizes[d.node_type] ?? 10;
      })
      .attr("font-family", "system-ui, sans-serif")
      .attr("font-weight", (d) =>
        d.node_type === "subject_root" || d.node_type === "module"
          ? "600"
          : "400",
      )
      .attr(
        "fill",
        (d) => (NODE_CONFIG[d.node_type] ?? NODE_CONFIG.subtopic).color,
      )
      .text((d) => nodeLabel(d, expandedRef.current));

    // ── Hover effects ───────────────────────────────────────────────────────
    nodeSel
      .on("mouseenter", function (_, d) {
        d3.select(this)
          .select<SVGCircleElement>("circle.main-circle")
          .attr("stroke-width", d.id === selectedTopicIdRef.current ? 5 : 3.5)
          .attr("filter", "brightness(1.25)");
      })
      .on("mouseleave", function (_, d) {
        d3.select(this)
          .select<SVGCircleElement>("circle.main-circle")
          .attr("stroke-width", d.id === selectedTopicIdRef.current ? 4 : 2)
          .attr("filter", null);
      });

    // ── Click / double-click ────────────────────────────────────────────────
    // Problem: browser fires click TWICE before dblclick, so a naive click
    // handler expands then immediately collapses the node on every dblclick.
    // Fix: delay single-click 250 ms. If a second click arrives inside that
    // window, cancel the timer — dblclick will fire cleanly on its own.
    nodeSel
      .on("click", (event, d) => {
        event.stopPropagation();

        if (clickTimerRef.current) {
          clearTimeout(clickTimerRef.current);
          clickTimerRef.current = null;
          return;
        }

        clickTimerRef.current = setTimeout(() => {
          clickTimerRef.current = null;
          handleNodeClick(d.id);
          nodeSel.select("text").text((n) => nodeLabel(n, expandedRef.current));
        }, 250);
      })
      .on("dblclick", (event, d) => {
        event.stopPropagation();
        handleNodeDblClick(d.id);
      });

    // ── Touch tap: D3 zoom intercepts touchstart/touchend before `click` fires
    // on mobile. We detect a "tap" ourselves: touchstart records position+time,
    // touchend checks movement < 10px + duration < 500ms → treat as a click.
    // Double-tap (two taps < 300ms apart) → open article reader.
    const touchState = new Map<number, { x: number; y: number; t: number }>();
    let lastTapTime = 0;

    nodeSel
      .on("touchstart", (event, _d) => {
        event.stopPropagation();
        const touch = event.changedTouches[0];
        touchState.set(touch.identifier, {
          x: touch.clientX,
          y: touch.clientY,
          t: Date.now(),
        });
      })
      .on("touchend", (event, d) => {
        event.stopPropagation();
        // Prevent the ghost mouse click that browsers fire ~300ms after touchend
        event.preventDefault();

        const touch = event.changedTouches[0];
        const start = touchState.get(touch.identifier);
        touchState.delete(touch.identifier);

        if (!start) return;

        const dx = Math.abs(touch.clientX - start.x);
        const dy = Math.abs(touch.clientY - start.y);
        const dt = Date.now() - start.t;

        // Not a tap if the finger moved > 10px or held > 500ms
        if (dx > 10 || dy > 10 || dt > 500) return;

        const now = Date.now();
        const isDoubleTap = now - lastTapTime < 300;
        lastTapTime = now;

        if (isDoubleTap) {
          // Cancel any pending single-tap action
          if (clickTimerRef.current) {
            clearTimeout(clickTimerRef.current);
            clickTimerRef.current = null;
          }
          handleNodeDblClick(d.id);
          return;
        }

        if (clickTimerRef.current) {
          clearTimeout(clickTimerRef.current);
          clickTimerRef.current = null;
          return;
        }

        clickTimerRef.current = setTimeout(() => {
          clickTimerRef.current = null;
          handleNodeClick(d.id);
          nodeSel.select("text").text((n) => nodeLabel(n, expandedRef.current));
        }, 250);
      });

    // ── Drag ────────────────────────────────────────────────────────────────
    const drag = d3
      .drag<SVGGElement, SimNode>()
      .on("start", (event, d) => {
        if (!event.active) sim.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) sim.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    nodeSel.call(drag);

    // ── Force Simulation (mirroring POC forceAtlas2Based physics) ──────────
    const sim = d3
      .forceSimulation<SimNode>(simNodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimEdge>(simEdges)
          .id((d) => d.id)
          .distance((d) => {
            const src = d.source as SimNode;
            const distances: Record<string, number> = {
              subject_root: 200,
              module: 150,
              topic: 110,
              subtopic: 75,
              sub_subtopic: 55,
            };
            return distances[src.node_type] ?? 80;
          })
          .strength(0.6),
      )
      .force(
        "charge",
        d3.forceManyBody<SimNode>().strength((d) => {
          const strengths: Record<string, number> = {
            subject_root: -500,
            module: -300,
            topic: -180,
            subtopic: -90,
            sub_subtopic: -60,
          };
          return strengths[d.node_type] ?? -90;
        }),
      )
      .force("center", d3.forceCenter(W / 2, H / 2).strength(0.08))
      .force(
        "collide",
        d3
          .forceCollide<SimNode>()
          .radius(
            (d) => (NODE_CONFIG[d.node_type] ?? NODE_CONFIG.subtopic).size + 22,
          )
          .strength(0.8),
      )
      .alphaDecay(0.025);

    simulationRef.current = sim;

    sim.on("tick", () => {
      edgeSel
        .attr("x1", (d) => (d.source as SimNode).x ?? 0)
        .attr("y1", (d) => (d.source as SimNode).y ?? 0)
        .attr("x2", (d) => (d.target as SimNode).x ?? 0)
        .attr("y2", (d) => (d.target as SimNode).y ?? 0);

      nodeSel.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => {
      sim.stop();
    };
  }, [visibleNodeIds, loading, handleNodeClick, handleNodeDblClick]);

  // ── Re-center when container becomes visible (mobile panel toggle) ─────────
  // Panel transitions from hidden (w=0) → visible: wait 80ms for layout,
  // then nudge simulation to new center. Full rebuild only if no sim yet.
  useEffect(() => {
    if (!containerVisible) return;
    const timer = setTimeout(() => {
      const wrapper = wrapperRef.current;
      const sim = simulationRef.current;
      if (!wrapper) return;

      const W = wrapper.clientWidth || 700;
      const H = wrapper.clientHeight || 500;

      if (sim) {
        // Lightweight: update center force + gentle alpha kick
        const cf = sim.force("center") as d3.ForceCenter<SimNode> | null;
        if (cf) {
          cf.x(W / 2).y(H / 2);
        }
        sim.alpha(0.2).restart();
      } else {
        // No simulation yet (first open) — do a full render
        setVisibleNodeIds((prev) => new Set(prev));
      }
    }, 80);
    return () => clearTimeout(timer);
  }, [containerVisible]);

  // ── ResizeObserver: lightweight resize on panel drag / window resize ──────
  // Does NOT rebuild the SVG or restart simulation from scratch.
  // Instead: updates center force → nodes smoothly drift to new center.
  // Full rebuild is only triggered when visible node set actually changes
  // (i.e., user clicks expand/collapse), not on every container resize.
  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    let timer: ReturnType<typeof setTimeout> | null = null;

    const observer = new ResizeObserver(() => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        const sim = simulationRef.current;
        const W = wrapper.clientWidth || 700;
        const H = wrapper.clientHeight || 500;

        if (sim) {
          // Update center force to new container midpoint
          const cf = sim.force("center") as d3.ForceCenter<SimNode> | null;
          if (cf) {
            cf.x(W / 2).y(H / 2);
          }
          // Small alpha so nodes drift gently, not a jarring jump
          sim.alpha(0.15).restart();
        } else {
          // Sim not initialised yet — full rebuild as fallback
          setVisibleNodeIds((prev) => new Set(prev));
        }
      }, 150);
    });

    observer.observe(wrapper);
    return () => {
      if (timer) clearTimeout(timer);
      observer.disconnect();
    };
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div
      className={cn(
        "relative flex flex-col w-full h-full rounded-lg border border-border bg-background overflow-hidden",
        className,
      )}
    >
      {/* ── Legend bar ───────────────────────────────────────────────────── */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-border bg-muted/20 flex-shrink-0 flex-wrap text-xs">
        <span className="text-muted-foreground font-medium tracking-wide uppercase">
          Hierarchy:
        </span>
        {LEGEND_ITEMS.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-muted-foreground">{item.label}</span>
          </div>
        ))}
        {/* Edge type legend */}
        <div className="ml-auto flex items-center gap-4 text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <svg width="18" height="6" aria-hidden>
              <line
                x1="0"
                y1="3"
                x2="18"
                y2="3"
                stroke="#4b5563"
                strokeWidth="1.5"
              />
            </svg>
            Contains
          </span>
          <span className="flex items-center gap-1.5">
            <svg width="18" height="6" aria-hidden>
              <line
                x1="0"
                y1="3"
                x2="18"
                y2="3"
                stroke="#f97316"
                strokeWidth="1.5"
                strokeDasharray="4,3"
              />
            </svg>
            Related
          </span>
        </div>
      </div>

      {/* ── Graph canvas ─────────────────────────────────────────────────── */}
      {/* touch-none: prevents browser from hijacking touch gestures for page scroll,
           letting D3 handle pan/pinch-zoom/drag natively on mobile */}
      <div
        ref={wrapperRef}
        className="relative flex-1 overflow-hidden touch-none"
      >
        {/* Loading overlay */}
        {loading && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-background/70 backdrop-blur-sm">
            <div className="h-8 w-8 rounded-full border-2 border-muted border-t-primary animate-spin" />
            <span className="text-sm text-muted-foreground">
              Loading knowledge graph…
            </span>
          </div>
        )}

        {/* Error overlay */}
        {!loading && error && (
          <div className="absolute inset-0 z-10 flex items-center justify-center p-6">
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-5 py-4 text-sm text-destructive text-center">
              {error}
            </div>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && stats.nodes === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <span className="text-5xl opacity-40" aria-hidden>
              🗺️
            </span>
            <p className="text-sm text-center">
              No graph data found for this subject.
            </p>
          </div>
        )}

        {/* D3 SVG canvas */}
        <svg
          ref={svgRef}
          className="w-full h-full"
          aria-label="Knowledge graph"
        />

        {/* Stats badge */}
        {!loading && !error && stats.nodes > 0 && (
          <div className="absolute bottom-3 left-3 rounded-md border border-border bg-background/80 backdrop-blur px-3 py-1.5 text-xs text-muted-foreground">
            <span className="text-primary font-medium">{stats.nodes}</span>{" "}
            nodes ·{" "}
            <span className="text-primary font-medium">{stats.edges}</span>{" "}
            edges ·{" "}
            <span className="text-muted-foreground/70">
              click to expand · drag to move
            </span>
          </div>
        )}

        {/* Hint: hint fades in only while no nodes expanded yet */}
        {!loading && !error && stats.nodes > 0 && (
          <div className="absolute top-3 right-3 rounded-md border border-border bg-background/70 backdrop-blur px-3 py-1.5 text-xs text-muted-foreground pointer-events-none">
            🔍 Pinch/scroll to zoom · Drag to pan
          </div>
        )}
      </div>
    </div>
  );
}
