/**
 * HomePageClient — the full homepage, rendered as a client component.
 *
 * Data contract:
 *   initialTodayArticles — today's Daily CA articles, pre-fetched server-side
 *   by the ISR page wrapper (src/app/page.tsx) so the HTML is baked with real
 *   content at build/revalidation time instead of being fetched in the browser.
 */

"use client";

import ArticleCard from "@/components/articles/article-card";
import { DailyCaTeaserWidget } from "@/components/daily-ca/daily-ca-teaser";
import { useSidebar } from "@/components/providers/sidebar-provider";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useArticles } from "@/lib/hooks/use-article";
import { cn } from "@/lib/utils";
import {
  ArrowRight,
  BookMarked,
  Bookmark,
  CheckCircle2,
  FileQuestion,
  FlaskConical,
  Folder,
  LayoutDashboard,
  Lightbulb,
  Newspaper,
  PenTool,
  Search,
  ShieldCheck,
  Sparkles,
  Trophy,
  Users,
  Zap,
} from "lucide-react";
import Link from "next/link";
import type { DailyCaArticleList } from "@/lib/api/daily-ca";
import type { Quiz } from "@/lib/types";
import { DailyQuizWidget } from "@/components/home/daily-quiz-widget";
import { HeroLiveCA } from "@/components/home/hero-live-ca";
import { HomepageWidget } from "@/components/research_agent/HomepageWidget";

// ─────────────────────────────────────────────────────────────────────────────
// KNOWLEDGE ORBITS GRAPH TEASER
// Pure CSS/SVG hierarchy preview — no D3, no deps.
// Shows Polity ↔ Economy as two subject trees with dashed cross-subject arrows.
// ─────────────────────────────────────────────────────────────────────────────

// viewBox: 0 0 100 82
// Left tree = Polity (violet), Right tree = Economy (blue/cyan)
// Cross-subject edges flagged with cross:true → dashed blue arrow

const GRAPH_NODES = [
  // ── Polity (left) ────────────────────────────────────────────────────────
  {
    id: "polity",
    label: "Indian\nPolity",
    x: 24,
    y: 11,
    r: 10,
    color: "#7c3aed",
    tc: "#fff",
    w: "700",
  },
  {
    id: "parliament",
    label: "Parliament",
    x: 12,
    y: 31,
    r: 8,
    color: "#8b5cf6",
    tc: "#fff",
    w: "600",
  },
  {
    id: "lok",
    label: "Lok Sabha",
    x: 5,
    y: 52,
    r: 6,
    color: "#a78bfa",
    tc: "#fff",
    w: "500",
  },
  {
    id: "rajya",
    label: "Rajya\nSabha",
    x: 16,
    y: 63,
    r: 6,
    color: "#c4b5fd",
    tc: "#4c1d95",
    w: "500",
  },
  {
    id: "fundrights",
    label: "Fundamental\nRights",
    x: 36,
    y: 33,
    r: 7.5,
    color: "#a78bfa",
    tc: "#fff",
    w: "600",
  },
  {
    id: "art19",
    label: "Art. 19–22",
    x: 29,
    y: 53,
    r: 5.5,
    color: "#ddd6fe",
    tc: "#4c1d95",
    w: "500",
  },
  {
    id: "dpsp",
    label: "DPSP",
    x: 43,
    y: 53,
    r: 5,
    color: "#ede9fe",
    tc: "#4c1d95",
    w: "500",
  },
  // ── Economy (right) ──────────────────────────────────────────────────────
  {
    id: "economy",
    label: "Indian\nEconomy",
    x: 76,
    y: 11,
    r: 10,
    color: "#0e7490",
    tc: "#fff",
    w: "700",
  },
  {
    id: "budget",
    label: "Union\nBudget",
    x: 63,
    y: 31,
    r: 8,
    color: "#0891b2",
    tc: "#fff",
    w: "600",
  },
  {
    id: "fiscal",
    label: "Fiscal\nPolicy",
    x: 55,
    y: 52,
    r: 6,
    color: "#67e8f9",
    tc: "#164e63",
    w: "500",
  },
  {
    id: "taxreform",
    label: "Tax\nReform",
    x: 68,
    y: 63,
    r: 6,
    color: "#a5f3fc",
    tc: "#164e63",
    w: "500",
  },
  {
    id: "monetary",
    label: "Monetary\nPolicy",
    x: 88,
    y: 33,
    r: 7.5,
    color: "#0284c7",
    tc: "#fff",
    w: "600",
  },
  {
    id: "rbi",
    label: "RBI",
    x: 82,
    y: 52,
    r: 5.5,
    color: "#7dd3fc",
    tc: "#0c4a6e",
    w: "500",
  },
  {
    id: "inflation",
    label: "Inflation",
    x: 94,
    y: 52,
    r: 5,
    color: "#bae6fd",
    tc: "#0c4a6e",
    w: "500",
  },
];

// cross:true → dashed blue arrow   cross:false → solid gray line
const GRAPH_EDGES = [
  // Polity hierarchy
  { from: "polity", to: "parliament", cross: false },
  { from: "polity", to: "fundrights", cross: false },
  { from: "parliament", to: "lok", cross: false },
  { from: "parliament", to: "rajya", cross: false },
  { from: "fundrights", to: "art19", cross: false },
  { from: "fundrights", to: "dpsp", cross: false },
  // Economy hierarchy
  { from: "economy", to: "budget", cross: false },
  { from: "economy", to: "monetary", cross: false },
  { from: "budget", to: "fiscal", cross: false },
  { from: "budget", to: "taxreform", cross: false },
  { from: "monetary", to: "rbi", cross: false },
  { from: "monetary", to: "inflation", cross: false },
  // Cross-subject (dashed blue) — Parliament approves Union Budget
  {
    from: "parliament",
    to: "budget",
    cross: true,
    label: "Appropriation\nBill",
  },
  // Cross-subject — Fiscal Policy impacts DPSP implementation
  { from: "fiscal", to: "dpsp", cross: true, label: "Welfare\nFunding" },
];

// HERO LIVE CA PANEL moved to components/home/hero-live-ca.tsx during G2,
// along with GS_BADGE_COLORS, which only that component used.

function KnowledgeGraphTeaser() {
  const nodeMap = Object.fromEntries(GRAPH_NODES.map((n) => [n.id, n]));

  return (
    <section className="relative overflow-hidden bg-card border-b border-border py-14 px-4">
      {/* Subtle dot-grid background */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.035]"
        style={{
          backgroundImage:
            "radial-gradient(circle, #6366f1 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      />

      <div className="container mx-auto max-w-7xl relative">
        {/* Header */}
        <div className="mb-10 text-center">
          <span className="mb-3 inline-flex items-center gap-2 rounded-full border border-violet-200 bg-violet-50 px-4 py-1.5 text-xs font-bold uppercase tracking-widest text-violet-600">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-500" />
            Knowledge Orbits
          </span>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
            Every topic is <span className="text-primary">connected</span>
          </h2>
          <p className="mt-3 text-base text-muted-foreground max-w-xl mx-auto">
            See how <strong className="text-foreground">Parliament</strong> and{" "}
            <strong className="text-foreground">Union Budget</strong> are two
            nodes in the same living knowledge graph.
          </p>
        </div>

        {/* Graph + sidebar layout */}
        <div className="flex flex-col lg:flex-row gap-8 items-stretch">
          {/* SVG Graph panel */}
          <div className="relative w-full lg:w-[58%] rounded-lg border border-border bg-muted/40 overflow-hidden shadow-sm">
            {/* Subject legend */}
            <div className="absolute top-3 left-3 flex flex-col gap-1">
              <span className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground">
                <span className="h-2 w-2 rounded-full bg-violet-500" />
                Indian Polity
              </span>
              <span className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground">
                <span className="h-2 w-2 rounded-full bg-cyan-500" />
                Indian Economy
              </span>
            </div>
            {/* Edge legend */}
            <div className="absolute top-3 right-3 flex flex-col items-end gap-1">
              <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                <svg width="18" height="6">
                  <line
                    x1="0"
                    y1="3"
                    x2="18"
                    y2="3"
                    stroke="#94a3b8"
                    strokeWidth="1.2"
                  />
                </svg>
                Hierarchy
              </span>
              <span className="flex items-center gap-1.5 text-[10px] text-blue-500">
                <svg width="18" height="6">
                  <line
                    x1="0"
                    y1="3"
                    x2="15"
                    y2="3"
                    stroke="#3b82f6"
                    strokeWidth="1.2"
                    strokeDasharray="2.5 1.5"
                  />
                  <polygon points="15,0 18,3 15,6" fill="#3b82f6" />
                </svg>
                Cross-subject
              </span>
            </div>

            <svg
              viewBox="0 0 100 82"
              className="w-full h-auto"
              preserveAspectRatio="xMidYMid meet"
            >
              <defs>
                <marker
                  id="arr-cross"
                  markerWidth="5"
                  markerHeight="5"
                  refX="4"
                  refY="2.5"
                  orient="auto"
                >
                  <polygon points="0,0 5,2.5 0,5" fill="#3b82f6" />
                </marker>
              </defs>

              {/* Edges — hierarchy first, then cross-subject on top */}
              {GRAPH_EDGES.map((e, i) => {
                const a = nodeMap[e.from];
                const b = nodeMap[e.to];
                if (!a || !b) return null;
                // Shorten line to node boundary so arrowhead touches circle edge
                const dx = b.x - a.x;
                const dy = b.y - a.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                const ux = dx / dist;
                const uy = dy / dist;
                const x1 = a.x + ux * a.r;
                const y1 = a.y + uy * a.r;
                const x2 = b.x - ux * (b.r + (e.cross ? 2.5 : 0));
                const y2 = b.y - uy * (b.r + (e.cross ? 2.5 : 0));
                const mx = (x1 + x2) / 2;
                const my = (y1 + y2) / 2;
                return (
                  <g key={i}>
                    <line
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke={e.cross ? "#3b82f6" : "#94a3b8"}
                      strokeWidth={e.cross ? "0.55" : "0.3"}
                      strokeDasharray={e.cross ? "1.4 0.9" : undefined}
                      opacity={e.cross ? 0.85 : 0.6}
                      markerEnd={e.cross ? "url(#arr-cross)" : undefined}
                    />
                    {e.cross && e.label && (
                      <text
                        x={mx}
                        y={my - 1}
                        textAnchor="middle"
                        fontSize="2"
                        fill="#3b82f6"
                        opacity="0.8"
                      >
                        {e.label.split("\n").map((ln: string, li: number) => (
                          <tspan key={li} x={mx} dy={li === 0 ? 0 : 2.2}>
                            {ln}
                          </tspan>
                        ))}
                      </text>
                    )}
                  </g>
                );
              })}

              {/* Nodes */}
              {GRAPH_NODES.map((n) => (
                <g key={n.id}>
                  <circle cx={n.x} cy={n.y} r={n.r} fill={n.color} />
                  {n.label
                    .split("\n")
                    .map((ln: string, li: number, arr: string[]) => (
                      <text
                        key={li}
                        x={n.x}
                        y={
                          n.y +
                          (li - (arr.length - 1) / 2) * (n.r > 7 ? 2.6 : 2.1)
                        }
                        textAnchor="middle"
                        dominantBaseline="middle"
                        fontSize={n.r >= 10 ? 2.6 : n.r >= 7.5 ? 2.2 : 2}
                        fontWeight={n.w}
                        fill={n.tc}
                      >
                        {ln}
                      </text>
                    ))}
                </g>
              ))}
            </svg>
          </div>

          {/* Right side — feature cards + CTA */}
          <div className="w-full lg:w-[42%] flex flex-col gap-4">
            {[
              {
                icon: "🔗",
                title: "Cross-Subject Links",
                desc: "Every concept auto-links to related topics across all UPSC subjects via semantic AI.",
              },
              {
                icon: "🧭",
                title: "Navigate by Meaning",
                desc: "Click any node to instantly load a book-quality UPSC article. No searching — just explore.",
              },
              {
                icon: "📡",
                title: "Live Current Affairs",
                desc: "Today's news is automatically wired to relevant syllabus nodes so nothing feels disconnected.",
              },
            ].map((card) => (
              <div
                key={card.title}
                className="rounded-lg border border-border bg-card p-5 hover:shadow-md hover:border-blue-200 transition-all"
              >
                <div className="mb-2 text-xl">{card.icon}</div>
                <h3 className="font-bold text-foreground text-sm mb-1">
                  {card.title}
                </h3>
                <p className="text-muted-foreground text-xs leading-relaxed">
                  {card.desc}
                </p>
              </div>
            ))}

            {/* CTA */}
            <Link href="/knowledge" className="mt-1">
              <button className="w-full group relative overflow-hidden rounded-lg bg-blue-600 hover:bg-blue-700 transition-colors px-6 py-4 font-bold text-white text-base shadow-md flex items-center justify-center gap-3">
                <span>Explore Knowledge Map</span>
                <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
                <span className="pointer-events-none absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-700 bg-gradient-to-r from-transparent via-white/10 to-transparent" />
              </button>
            </Link>

            <p className="text-center text-xs text-muted-foreground">
              {GRAPH_NODES.length} nodes · {GRAPH_EDGES.length} connections ·
              fully interactive
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// HomePageClient — receives pre-fetched ISR data from the server page wrapper
// ─────────────────────────────────────────────────────────────────────────────

export default function HomePageClient({
  initialTodayArticles,
  initialTodayQuiz = null,
}: {
  initialTodayArticles: DailyCaArticleList[];
  /** Today's Daily Public Quiz, pre-fetched via ISR. null = not yet generated. */
  initialTodayQuiz?: Quiz | null;
}) {
  const { data: articlesData, isLoading } = useArticles({ page_size: 9 });
  const articlesArray = articlesData?.results || [];
  const articles = articlesArray.slice(0, 9);
  const { isCollapsed } = useSidebar();

  // Articles are pre-fetched server-side via ISR — no useEffect needed.
  // loading=false means the widgets render content immediately on first paint.
  const todayArticles = initialTodayArticles;

  return (
    <div className="flex flex-col min-h-screen bg-card">
      {/*
          WRAPPER FOR TOP SECTIONS (Pushed by Sidebar)
          Only applies padding for the sections within the sidebar's typical reach.
      */}
      <div
        className={cn(
          "transition-all duration-300 ease-in-out",
          isCollapsed ? "lg:pl-20" : "lg:pl-64",
        )}
      >
        {/* 1. HERO — 2-column: pitch (left) + live CA preview (right) */}
        <section className="relative overflow-hidden border-b border-border bg-background">
          {/* Soft dot grid */}
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.03]"
            style={{
              backgroundImage:
                "radial-gradient(circle, #3b82f6 1px, transparent 1px)",
              backgroundSize: "24px 24px",
            }}
          />

          <div className="container relative mx-auto px-4 max-w-7xl">
            <div className="flex flex-col lg:flex-row items-center gap-10 py-14 lg:py-20">
              {/* ── LEFT: Value Prop ── */}
              <div className="lg:w-[54%] text-center lg:text-left">
                <Badge className="mb-5 px-4 py-1.5 bg-blue-100 text-blue-600 border-blue-200 hover:bg-blue-100 cursor-default shadow-sm border inline-flex">
                  <Sparkles className="h-3.5 w-3.5 mr-2" />
                  8-Agent AI Research · UPSC Focused
                </Badge>

                <h1 className="text-4xl sm:text-5xl lg:text-6xl font-semibold text-foreground tracking-tight mb-5 leading-[1.1]">
                  Your Personal{" "}
                  <span className="text-primary">AI Research Maestro</span>
                </h1>

                <p className="text-base md:text-lg text-muted-foreground mb-8 max-w-xl mx-auto lg:mx-0 leading-relaxed">
                  Ask any UPSC question — our{" "}
                  <span className="text-foreground font-semibold">
                    8-agent AI pipeline
                  </span>{" "}
                  researches, verifies, and streams a cited report in real time.
                  Syllabus-mapped, source-verified, instantly ready.
                </p>

                <div className="grid grid-cols-2 gap-3 mb-10 max-w-md mx-auto lg:mx-0">
                  <Link href="/research_agent" className="block">
                    <Button
                      size="lg"
                      className="w-full h-11 px-4 text-sm bg-blue-600 hover:bg-blue-700 shadow-lg shadow-blue-950/10 gap-2 group"
                    >
                      <FlaskConical className="h-4 w-4" />
                      Deep Research
                    </Button>
                  </Link>
                  <Link href="/daily-ca" className="block">
                    <Button
                      size="lg"
                      variant="outline"
                      className="w-full h-11 px-4 text-sm text-emerald-700 border-emerald-200 bg-emerald-50 hover:bg-emerald-100 gap-2"
                    >
                      <Newspaper className="h-4 w-4" />
                      Today&apos;s CA
                    </Button>
                  </Link>
                  <Link
                    href={
                      initialTodayQuiz
                        ? `/assessment/${initialTodayQuiz.id}/intro`
                        : "/assessment"
                    }
                    className="block"
                  >
                    <Button
                      size="lg"
                      variant="outline"
                      className="w-full h-11 px-4 text-sm text-violet-700 border-violet-200 bg-violet-50 hover:bg-violet-100 gap-2"
                    >
                      <FileQuestion className="h-4 w-4" />
                      Try a Quiz
                    </Button>
                  </Link>
                  <Link href="/generate" className="block">
                    <Button
                      size="lg"
                      variant="outline"
                      className="w-full h-11 px-4 text-sm text-foreground border-border bg-muted/40 hover:bg-slate-100 gap-2"
                    >
                      <Sparkles className="h-4 w-4" />
                      Generate Article
                    </Button>
                  </Link>
                </div>

                {/* Trust stats */}
                <div className="flex flex-wrap items-center justify-center lg:justify-start gap-6 sm:gap-8 opacity-70">
                  {[
                    { val: "100%", label: "Syllabus Coverage" },
                    { val: "Verified", label: "NCERT Sources" },
                    { val: "Daily", label: "CA Integration" },
                    { val: "AI RAG", label: "Powered" },
                  ].map((s, i, arr) => (
                    <div
                      key={s.label}
                      className="flex items-center gap-6 sm:gap-8"
                    >
                      <div className="flex flex-col items-center lg:items-start gap-0.5">
                        <span className="text-xl font-semibold text-foreground">
                          {s.val}
                        </span>
                        <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-bold">
                          {s.label}
                        </span>
                      </div>
                      {i < arr.length - 1 && (
                        <div className="w-px h-7 bg-slate-200 hidden sm:block" />
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* ── RIGHT: Research Agent Widget + Live CA Preview ── */}
              {/* G2: flex-col-reverse below lg puts today's CA above the
                  research-agent widget on phones — leading with content beats
                  leading with a tool. Desktop order is unchanged. */}
              <div className="lg:w-[46%] w-full max-w-md mx-auto lg:mx-0 flex flex-col-reverse lg:flex-col gap-4">
                <HomepageWidget />
                <HeroLiveCA
                  articles={todayArticles.slice(0, 5)}
                  loading={false}
                />
              </div>
            </div>
          </div>
        </section>

        {/* 2. DAILY CA TEASER — full date-navigable feed strip */}
        {/* todayArticles is server-baked, so DailyCaTeaserWidget skips its own initial fetch */}
        <DailyCaTeaserWidget initialArticles={todayArticles} />

        {/* 3. DAILY QUIZ WIDGET — public quiz, no login needed */}
        {/* initialTodayQuiz is server-baked via ISR — skips redundant first fetch */}
        <DailyQuizWidget initialTodayQuiz={initialTodayQuiz} />

        {/* 4. KNOWLEDGE GRAPH TEASER — visual wow */}
        <KnowledgeGraphTeaser />
      </div>

      {/* 2. RECENT CONTRIBUTIONS: Actual functional data */}
      <section className="py-14 sm:py-20 bg-muted/40">
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row items-baseline justify-between mb-12 gap-4">
            <div>
              <h2 className="text-3xl font-bold text-foreground mb-2">
                Latest Knowledge Orbits
              </h2>
              <p className="text-muted-foreground">
                Freshly generated articles by our community and AI.
              </p>
            </div>
            <Link
              href="/articles"
              className="flex items-center text-blue-600 font-bold hover:gap-2 transition-all"
            >
              View All Insights <ArrowRight className="h-4 w-4 ml-2" />
            </Link>
          </div>

          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => (
                <Skeleton
                  key={i}
                  className="h-[300px] w-full rounded-lg bg-card shadow-sm"
                />
              ))}
            </div>
          ) : articles.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {articles.map((article) => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          ) : (
            <div className="text-center py-20 bg-card border-2 border-dashed border-border rounded-lg">
              <Lightbulb className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground font-medium">
                No articles yet. Be the first to orbit!
              </p>
              <Link
                href="/generate"
                className="mt-4 block text-blue-600 font-bold hover:underline"
              >
                Start Generating →
              </Link>
            </div>
          )}
        </div>
      </section>

      {/* 3. PLATFORM CORE FEATURES: Luring and Informative */}
      <section className="py-14 sm:py-20 bg-card border-y border-border">
        <div className="container mx-auto px-4 text-center mb-16">
          <h2 className="text-4xl font-semibold text-foreground mb-6">
            The All-in-One UPSC OS
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            We don't just provide material; we provide an ecosystem that evolves
            with your preparation needs.
          </p>
        </div>

        <div className="container mx-auto px-4 grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Feature 1 */}
          <div className="p-8 rounded-lg bg-muted/40 border border-border transition-all hover:bg-card hover:shadow-2xl hover:shadow-slate-200/50 hover:-translate-y-1">
            <div className="h-12 w-12 bg-blue-100 rounded-lg flex items-center justify-center mb-6">
              <BookMarked className="h-6 w-6 text-blue-600" />
            </div>
            <h3 className="text-xl font-bold text-foreground mb-3">
              Sync-Notebook
            </h3>
            <p className="text-sm text-muted-foreground mb-6 font-medium leading-relaxed">
              Save any generated article instantly to your personalized
              dashboard. Highlight, annotate, and review your progress over
              time.
            </p>
            <Link
              href="/notebook"
              className="text-blue-600 text-sm font-bold flex items-center gap-1 group"
            >
              Open Notebook{" "}
              <ArrowRight className="h-3 w-3 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>

          {/* Feature 2 */}
          <div className="p-8 rounded-lg bg-muted/40 border border-border transition-all hover:bg-card hover:shadow-2xl hover:shadow-slate-200/50 hover:-translate-y-1">
            <div className="h-12 w-12 bg-emerald-100 rounded-lg flex items-center justify-center mb-6">
              <Zap className="h-6 w-6 text-emerald-600" />
            </div>
            <h3 className="text-xl font-bold text-foreground mb-3">
              Smart-Recall Quizzes
            </h3>
            <p className="text-sm text-muted-foreground mb-6 font-medium leading-relaxed">
              Every article comes with a RAG-powered quiz. Don't just
              read—verify your understanding with syllabus-mapped questions.
            </p>
            <Link
              href="/assessment"
              className="text-emerald-600 text-sm font-bold flex items-center gap-1 group"
            >
              Start Practice{" "}
              <ArrowRight className="h-3 w-3 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>

          {/* Feature 3 */}
          <div className="p-8 rounded-lg bg-muted/40 border border-border transition-all hover:bg-card hover:shadow-2xl hover:shadow-slate-200/50 hover:-translate-y-1">
            <div className="h-12 w-12 bg-purple-100 rounded-lg flex items-center justify-center mb-6">
              <Search className="h-6 w-6 text-purple-600" />
            </div>
            <h3 className="text-xl font-bold text-foreground mb-3">
              Syllabus Mapping
            </h3>
            <p className="text-sm text-muted-foreground mb-6 font-medium leading-relaxed">
              No more irrelevant topics. Every insight is tagged to specific
              UPSC pillars (Polity, History, Ethics, etc.) to keep you focused.
            </p>
            <Link
              href="/topics"
              className="text-purple-600 text-sm font-bold flex items-center gap-1 group"
            >
              Explore Pillars{" "}
              <ArrowRight className="h-3 w-3 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>
      </section>

      {/* 4. THE FUTURE: MISSION ROADMAP (Light Theme) */}
      <section className="py-14 sm:py-20 bg-blue-50/30 overflow-hidden relative">
        <div className="container relative mx-auto px-4">
          <div className="flex flex-col lg:flex-row items-center gap-16">
            <div className="lg:w-1/2">
              <Badge className="bg-blue-100 text-blue-600 border-none mb-6">
                BEYOND GENERATION
              </Badge>
              <h2 className="text-4xl font-bold text-foreground mb-8 leading-tight">
                Complete UPSC Mastery with <br />
                AI Ecosystem
              </h2>
              <p className="text-lg text-muted-foreground mb-10 leading-relaxed">
                We are building the future of UPSC preparation. Our upcoming
                modules will provide a full-spectrum solution from Prelims to
                Interview.
              </p>

              <div className="space-y-6">
                <div className="flex gap-4 p-4 rounded-lg bg-card border border-border shadow-sm transition-all hover:shadow-md">
                  <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center shrink-0">
                    <PenTool className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <h4 className="font-bold text-foreground flex items-center gap-2">
                      Mains Answer Evaluation{" "}
                      <Badge
                        variant="outline"
                        className="text-[10px] h-4 text-blue-600 border-blue-600"
                      >
                        COMING SOON
                      </Badge>
                    </h4>
                    <p className="text-sm text-muted-foreground">
                      Submit your hand-written answers; our AI evaluates them
                      based on UPSC parameters like Structure, Content, and
                      Relevance.
                    </p>
                  </div>
                </div>

                <div className="flex gap-4 p-4 rounded-lg bg-card border border-border shadow-sm transition-all hover:shadow-md">
                  <div className="h-10 w-10 rounded-lg bg-emerald-100 flex items-center justify-center shrink-0">
                    <Trophy className="h-5 w-5 text-emerald-600" />
                  </div>
                  <div>
                    <h4 className="font-bold text-foreground flex items-center gap-2">
                      All-India Test Series{" "}
                      <Badge
                        variant="outline"
                        className="text-[10px] h-4 text-emerald-600 border-emerald-600"
                      >
                        Q2 2026
                      </Badge>
                    </h4>
                    <p className="text-sm text-muted-foreground">
                      Compete with thousands. Get AI-powered bottleneck analysis
                      to find which subjects are holding back your Prelims
                      score.
                    </p>
                  </div>
                </div>

                <div className="flex gap-4 p-4 rounded-lg bg-card border border-border shadow-sm transition-all hover:shadow-md">
                  <div className="h-10 w-10 rounded-lg bg-indigo-100 flex items-center justify-center shrink-0">
                    <Users className="h-5 w-5 text-indigo-600" />
                  </div>
                  <div>
                    <h4 className="font-bold text-foreground flex items-center gap-2">
                      AI Interview Mentor{" "}
                      <Badge
                        variant="outline"
                        className="text-[10px] h-4 text-indigo-600 border-indigo-600"
                      >
                        Q3 2026
                      </Badge>
                    </h4>
                    <p className="text-sm text-muted-foreground">
                      Personalized mock interviews based on your DAF, with
                      instant feedback on tone, body language, and content
                      depth.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="lg:w-1/2 relative w-full">
              <div className="p-10 rounded-lg bg-card border border-border shadow-2xl space-y-8">
                <h3 className="text-2xl font-bold text-foreground">
                  Why wait?
                </h3>
                <p className="text-muted-foreground leading-relaxed">
                  Start building your knowledge base today and be the first to
                  access our premium evaluation tools.
                </p>

                <ul className="space-y-4">
                  <li className="flex items-center gap-3 text-sm text-foreground font-medium">
                    <div className="bg-blue-100 p-1 rounded-full">
                      <CheckCircle2 className="h-4 w-4 text-blue-600" />
                    </div>{" "}
                    Verified UPSC Syllabus Mapping
                  </li>
                  <li className="flex items-center gap-3 text-sm text-foreground font-medium">
                    <div className="bg-blue-100 p-1 rounded-full">
                      <CheckCircle2 className="h-4 w-4 text-blue-600" />
                    </div>{" "}
                    Personal Notebook Sync
                  </li>
                  <li className="flex items-center gap-3 text-sm text-foreground font-medium">
                    <div className="bg-blue-100 p-1 rounded-full">
                      <CheckCircle2 className="h-4 w-4 text-blue-600" />
                    </div>{" "}
                    AI-powered Doubt Clearance
                  </li>
                  <li className="flex items-center gap-3 text-sm text-foreground font-medium">
                    <div className="bg-blue-100 p-1 rounded-full">
                      <CheckCircle2 className="h-4 w-4 text-blue-600" />
                    </div>{" "}
                    Detailed Performance Analytics
                  </li>
                </ul>

                <Button
                  size="lg"
                  asChild
                  className="w-full h-14 bg-slate-900 text-white hover:bg-slate-800 font-bold border-none transition-all shadow-lg shadow-slate-200"
                >
                  <Link href="/auth/register">Secure Early Access</Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 5. FINISH: Ecosystem Links (Functional Buttons) */}
      <section className="py-14 sm:py-20 bg-card">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Link href="/dashboard" className="group">
              <div className="p-8 bg-muted/40 border border-border rounded-lg transition-all hover:bg-card hover:shadow-2xl hover:shadow-blue-600/5 hover:border-blue-200">
                <LayoutDashboard className="h-8 w-8 text-blue-600 mb-6 group-hover:scale-110 transition-transform" />
                <h4 className="font-bold text-foreground text-lg">
                  Personal Dashboard
                </h4>
                <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                  Track your entire UPSC journey in one place.
                </p>
              </div>
            </Link>

            <Link href="/current-affairs" className="group">
              <div className="p-8 bg-muted/40 border border-border rounded-lg transition-all hover:bg-card hover:shadow-2xl hover:shadow-emerald-600/5 hover:border-emerald-200">
                <Newspaper className="h-8 w-8 text-emerald-600 mb-6 group-hover:scale-110 transition-transform" />
                <h4 className="font-bold text-foreground text-lg">
                  Daily Current Affairs
                </h4>
                <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                  UPSC-centric news distilled for your prep.
                </p>
              </div>
            </Link>

            <Link href="/topics" className="group">
              <div className="p-8 bg-muted/40 border border-border rounded-lg transition-all hover:bg-card hover:shadow-2xl hover:shadow-purple-600/5 hover:border-purple-200">
                <Folder className="h-8 w-8 text-purple-600 mb-6 group-hover:scale-110 transition-transform" />
                <h4 className="font-bold text-foreground text-lg">
                  Syllabus Explorer
                </h4>
                <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                  Deep dive into every pillar of the exam.
                </p>
              </div>
            </Link>

            <Link href="/bookmarks" className="group">
              <div className="p-8 bg-muted/40 border border-border rounded-lg transition-all hover:bg-card hover:shadow-2xl hover:shadow-pink-600/5 hover:border-pink-200">
                <Bookmark className="h-8 w-8 text-pink-600 mb-6 group-hover:scale-110 transition-transform" />
                <h4 className="font-bold text-foreground text-lg">
                  Saved Articles
                </h4>
                <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                  Quickly access bits of gold you've discovered.
                </p>
              </div>
            </Link>
          </div>
        </div>
      </section>

      {/* 6. FAQ SECTION: For Clarity & Conversion */}
      <section
        id="faqs"
        className="py-14 sm:py-20 bg-card border-t border-border"
      >
        <div className="container mx-auto px-4 max-w-4xl">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-foreground mb-4">
              Frequently Asked Questions
            </h2>
            <p className="text-muted-foreground">
              Everything you need to know about TheKnowledgeOrbits
            </p>
          </div>

          <Accordion type="single" collapsible className="w-full space-y-4">
            <AccordionItem
              value="item-1"
              className="border border-border rounded-lg px-6 bg-muted/40"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-foreground text-left">
                How does TheKnowledgeOrbits help in UPSC preparation?
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground leading-relaxed pb-6">
                TheKnowledgeOrbits is a specialized UPSC Operating System.
                Unlike random internet searches, we provide context-aware,
                syllabus-mapped articles generated using AI-RAG technology. It
                helps you quickly cover static topics and link them with current
                affairs, followed by instant quizzes for retention.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-2"
              className="border border-border rounded-lg px-6 bg-muted/40"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-foreground text-left">
                What is RAG technology and why is it better?
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground leading-relaxed pb-6">
                RAG (Retrieval-Augmented Generation) is our secret sauce.
                Instead of just "hallucinating" facts like standard AI, our
                system first fetches relevant data from multiple verified UPSC
                sources (NCERTs, PIB, Standard Textbooks) and then synthesizes
                an answer. This ensures 99% factual accuracy and relevance.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-3"
              className="border border-border rounded-lg px-6 bg-muted/40"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-foreground text-left">
                Are the articles based strictly on the UPSC syllabus?
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground leading-relaxed pb-6">
                Yes. Every article generated is tagged to specific GS pillars
                (GS 1-4) or Prelims subjects. Our AI is tuned to favor
                UPSC-style language and importance-weighting, ensuring you don't
                waste time on non-essential trivia.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-4"
              className="border border-border rounded-lg px-6 bg-muted/40"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-foreground text-left">
                Can I really use this for Mains Answer Writing?
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground leading-relaxed pb-6">
                Absolutely. The "Knowledge Orbits" you generate follow a
                structured format: Context, Key Dimensions, Impact, and
                Conclusion. These structure-bits reflect the standard framework
                required for Mains answers, helping you build a mental template
                for every topic.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-5"
              className="border border-border rounded-lg px-6 bg-muted/40"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-foreground text-left">
                How frequently is the Current Affairs knowledge base updated?
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground leading-relaxed pb-6">
                Our "Current Affairs Engine" scans major newspapers (The Hindu,
                Indian Express) and government sources (PIB, Sansad TV) daily.
                New insights are available to the AI within hours of their
                publication, keeping your knowledge fresh.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-6"
              className="border border-border rounded-lg px-6 bg-muted/40"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-foreground text-left">
                What is the "Sync-Notebook" feature?
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground leading-relaxed pb-6">
                Sync-Notebook is your digital library. Any article you generate
                can be saved with one click. These are stored securely on our
                cloud, allow you to highlight key points, and are indexed for
                quick searching during revision sessions.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-7"
              className="border border-border rounded-lg px-6 bg-muted/40"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-foreground text-left">
                Do the quizzes cover previous year questions (PYQs)?
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground leading-relaxed pb-6">
                While we focus on AI-generated questions mapped to your current
                reading, our system analysis logic includes PYQ patterns to
                ensure the difficulty and type of questions reflect actual UPSC
                trends.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-8"
              className="border border-border rounded-lg px-6 bg-muted/40"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-foreground text-left">
                Is the platform mobile-responsive?
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground leading-relaxed pb-6">
                Yes. The platform is designed for cross-device usage. You can
                generate articles on your laptop and take quizzes on your phone
                while commuting.
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </section>

      {/* 7. TRUST & SECURITY: Final Assurance */}
      <section className="py-16 border-y border-border bg-muted/40/30">
        <div className="container mx-auto px-4 flex flex-wrap justify-center gap-12 items-center opacity-70 grayscale-0">
          <div className="flex items-center gap-2 text-foreground">
            <ShieldCheck className="h-5 w-5 text-blue-600" />
            <span className="font-bold uppercase tracking-tighter text-sm">
              NCERT Verified
            </span>
          </div>
          <div className="flex items-center gap-2 text-foreground">
            <ShieldCheck className="h-5 w-5 text-blue-600" />
            <span className="font-bold uppercase tracking-tighter text-sm">
              PIB & Hindu Sourced
            </span>
          </div>
          <div className="flex items-center gap-2 text-foreground">
            <ShieldCheck className="h-5 w-5 text-blue-600" />
            <span className="font-bold uppercase tracking-tighter text-sm">
              Secure-Data-Notebook
            </span>
          </div>
          <div className="flex items-center gap-2 text-foreground">
            <ShieldCheck className="h-5 w-5 text-blue-600" />
            <span className="font-bold uppercase tracking-tighter text-sm">
              AI-Powered Validation
            </span>
          </div>
        </div>
      </section>
    </div>
  );
}
