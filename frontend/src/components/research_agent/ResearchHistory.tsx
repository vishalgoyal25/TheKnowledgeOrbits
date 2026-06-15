"use client";

import Link from "next/link";
import {
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronRight,
} from "lucide-react";
import { useResearchHistory } from "@/lib/hooks/use-research-history";
import type { HistoryListItem, SessionStatus } from "@/types/research_agent";

// ── Status badge ──────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<
  SessionStatus,
  { label: string; icon: React.ReactNode; className: string }
> = {
  pending: {
    label: "Pending",
    icon: <Clock className="w-3 h-3" />,
    className: "bg-gray-100 text-gray-600",
  },
  running: {
    label: "Running",
    icon: <Loader2 className="w-3 h-3 animate-spin" />,
    className: "bg-blue-100 text-blue-700",
  },
  completed: {
    label: "Completed",
    icon: <CheckCircle2 className="w-3 h-3" />,
    className: "bg-green-100 text-green-700",
  },
  failed: {
    label: "Failed",
    icon: <XCircle className="w-3 h-3" />,
    className: "bg-red-100 text-red-700",
  },
  cancelled: {
    label: "Cancelled",
    icon: <XCircle className="w-3 h-3" />,
    className: "bg-gray-100 text-gray-500",
  },
};

function StatusBadge({ status }: { status: SessionStatus }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${cfg.className}`}
    >
      {cfg.icon}
      {cfg.label}
    </span>
  );
}

function ConfidencePip({ score }: { score: number | null }) {
  if (score === null) return null;
  const pct = Math.round(score * 100);
  const color =
    score >= 0.8
      ? "text-green-600"
      : score >= 0.6
        ? "text-orange-500"
        : "text-red-500";
  return (
    <span className={`text-xs font-semibold tabular-nums ${color}`}>
      {pct}%
    </span>
  );
}

// ── Session card ──────────────────────────────────────────────────────────────

function SessionCard({ item }: { item: HistoryListItem }) {
  const date = new Date(item.created_at).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  return (
    <Link
      href={`/research_agent/history/${item.id}`}
      className="group flex items-center gap-4 rounded-xl border border-gray-200 bg-white px-4 py-3.5 shadow-sm hover:shadow-md hover:border-gray-300 transition-all duration-150"
    >
      {/* Query text */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 line-clamp-2 leading-snug group-hover:text-blue-700 transition-colors">
          {item.query}
        </p>
        <p className="mt-1 text-[11px] text-gray-400">{date}</p>
      </div>

      {/* Right-side metadata */}
      <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
        <StatusBadge status={item.status} />
        <ConfidencePip score={item.confidence_score} />
      </div>

      <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-gray-500 flex-shrink-0 transition-colors" />
    </Link>
  );
}

// ── Skeletons ─────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="flex items-center gap-4 rounded-xl border border-gray-100 bg-white px-4 py-3.5 animate-pulse">
      <div className="flex-1 space-y-2">
        <div className="h-3.5 w-3/4 rounded bg-gray-200" />
        <div className="h-2.5 w-1/4 rounded bg-gray-100" />
      </div>
      <div className="w-16 h-5 rounded-full bg-gray-200" />
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ResearchHistory() {
  const { items, isLoading, error, hasNextPage, requiresAuth, loadNextPage } =
    useResearchHistory();

  // Unauthenticated state
  if (requiresAuth) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-gray-200 py-16 text-center">
        <p className="text-sm text-gray-500">
          Sign in to see your research history
        </p>
        <Link
          href="/login"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          Sign in
        </Link>
      </div>
    );
  }

  // Initial loading
  if (isLoading && items.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  // Error state
  if (error && items.length === 0) {
    return (
      <div className="rounded-xl border border-red-100 bg-red-50 px-5 py-8 text-center text-sm text-red-600">
        {error}
      </div>
    );
  }

  // Empty state
  if (!isLoading && items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-gray-200 py-16 text-center">
        <p className="text-sm text-gray-500">
          No research yet — ask your first question above
        </p>
        <Link
          href="/research_agent"
          className="text-xs text-blue-600 underline hover:text-blue-800"
        >
          Go to Research Agent →
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => (
        <SessionCard key={item.id} item={item} />
      ))}

      {/* Load more */}
      {hasNextPage && (
        <button
          type="button"
          onClick={loadNextPage}
          disabled={isLoading}
          className="mt-2 w-full rounded-xl border border-gray-200 py-2.5 text-sm text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading…
            </span>
          ) : (
            "Load more"
          )}
        </button>
      )}

      {/* Inline error on pagination failure */}
      {error && items.length > 0 && (
        <p className="text-center text-xs text-red-500">{error}</p>
      )}
    </div>
  );
}
