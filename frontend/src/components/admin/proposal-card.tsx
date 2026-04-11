"use client";

import { Proposal } from "@/lib/api/daily-ca-admin";

interface Props {
  proposal: Proposal;
  index: number;
  selected: boolean;
  disabled: boolean;
  onToggle: (id: string) => void;
}

const GS_COLORS: Record<string, string> = {
  GS1: "bg-purple-100 text-purple-800",
  GS2: "bg-blue-100 text-blue-800",
  GS3: "bg-green-100 text-green-800",
  GS4: "bg-orange-100 text-orange-800",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-700",
  approved: "bg-green-100 text-green-700",
  generated: "bg-blue-100 text-blue-700",
  failed: "bg-red-100 text-red-700",
  queued_next_run: "bg-gray-100 text-gray-600",
  rejected: "bg-gray-200 text-gray-500",
};

export function ProposalCard({
  proposal,
  index,
  selected,
  disabled,
  onToggle,
}: Props) {
  const relevancePct = Math.round((proposal.relevance_score / 10) * 100);
  const isDisabled = disabled && !selected;

  return (
    <div
      className={`relative rounded-xl border p-4 transition-all cursor-pointer
        ${
          selected
            ? "border-blue-500 bg-blue-50 shadow-md"
            : "border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm"
        }
        ${isDisabled ? "opacity-40 cursor-not-allowed" : ""}
      `}
      onClick={() => !isDisabled && onToggle(proposal.id)}
    >
      {/* Checkbox */}
      <div className="absolute top-3 right-3">
        <input
          type="checkbox"
          checked={selected}
          disabled={isDisabled}
          onChange={() => onToggle(proposal.id)}
          onClick={(e) => e.stopPropagation()}
          className="w-4 h-4 accent-blue-600 cursor-pointer"
        />
      </div>

      {/* Header row */}
      <div className="flex items-center gap-2 mb-2 pr-6">
        <span className="text-xs font-bold text-gray-400">#{index + 1}</span>
        {proposal.gs_paper && (
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
              GS_COLORS[proposal.gs_paper] || "bg-gray-100 text-gray-600"
            }`}
          >
            {proposal.gs_paper}
          </span>
        )}
        {proposal.subject_name && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 truncate max-w-[120px]">
            {proposal.subject_name}
          </span>
        )}
        <span
          className={`ml-auto text-xs px-2 py-0.5 rounded-full ${
            STATUS_COLORS[proposal.status] || "bg-gray-100 text-gray-600"
          }`}
        >
          {proposal.status}
        </span>
      </div>

      {/* Title */}
      <p className="font-semibold text-gray-900 text-sm leading-snug line-clamp-2 mb-1">
        {proposal.title}
      </p>

      {/* Description */}
      <p className="text-xs text-gray-500 line-clamp-3 mb-3">
        {proposal.description}
      </p>

      {/* Relevance bar */}
      <div className="mb-2">
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span>Relevance</span>
          <span className="font-medium text-gray-600">
            {proposal.relevance_score.toFixed(1)}/10
          </span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-1.5">
          <div
            className="h-1.5 rounded-full bg-gradient-to-r from-blue-400 to-blue-600 transition-all"
            style={{ width: `${relevancePct}%` }}
          />
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-gray-400">
        <span>
          {proposal.source_count} source{proposal.source_count !== 1 ? "s" : ""}
        </span>
        {proposal.topic_name && (
          <span className="truncate max-w-[150px] text-right text-gray-400">
            {proposal.topic_name}
          </span>
        )}
      </div>
    </div>
  );
}
