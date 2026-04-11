"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ProposalCard } from "@/components/admin/proposal-card";
import { GenerationProgressModal } from "@/components/admin/generation-progress-modal";
import {
  getProposals,
  approveProposals,
  triggerGeneration,
  Proposal,
} from "@/lib/api/daily-ca-admin";

const MAX_SELECT = 10;

function todayStr() {
  return new Date().toISOString().split("T")[0];
}

export default function ProposalsPage() {
  const router = useRouter();
  const [date, setDate] = useState(todayStr());
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  const fetchProposals = async (d: string) => {
    setLoading(true);
    setError(null);
    setSelected(new Set());
    try {
      const data = await getProposals(d);
      setProposals(data.proposals);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load proposals");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProposals(date);
  }, [date]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < MAX_SELECT) {
        next.add(id);
      }
      return next;
    });
  };

  const handleApprove = async () => {
    if (selected.size === 0) return;
    setApproving(true);
    setError(null);
    try {
      await approveProposals(Array.from(selected));
      // Trigger background generation immediately after approval
      await triggerGeneration(date);
      setShowModal(true);
    } catch (e: unknown) {
      setError(
        e instanceof Error
          ? e.message
          : "Approval or generation trigger failed",
      );
    } finally {
      setApproving(false);
    }
  };

  const pendingProposals = proposals.filter((p) =>
    ["pending", "failed"].includes(p.status),
  );
  const otherProposals = proposals.filter(
    (p) => !["pending", "failed"].includes(p.status),
  );
  const remaining = MAX_SELECT - selected.size;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              Daily CA Proposals
            </h1>
            <p className="text-sm text-gray-500">
              Select up to 10 proposals to approve for generation
            </p>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={() => router.push(`/admin/daily-ca/review/${date}`)}
              className="text-sm text-blue-600 hover:underline px-3 py-2"
            >
              Review Articles →
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Error */}
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading ? (
          <div className="text-center py-20 text-gray-400">
            Loading proposals...
          </div>
        ) : proposals.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-500 mb-2">No proposals found for {date}</p>
            <p className="text-sm text-gray-400">
              Run{" "}
              <code className="bg-gray-100 px-1 rounded">
                python manage.py generate_ca_proposals --date {date}
              </code>
            </p>
          </div>
        ) : (
          <>
            {/* Selection counter */}
            <div className="mb-4 flex items-center gap-3">
              <span className="text-sm font-medium text-gray-700">
                <span className="text-blue-600 font-bold">{selected.size}</span>
                /{MAX_SELECT} selected
              </span>
              {selected.size < MAX_SELECT && selected.size > 0 && (
                <span className="text-xs text-gray-400">
                  Select {remaining} more
                </span>
              )}
              {selected.size === MAX_SELECT && (
                <span className="text-xs text-green-600 font-medium">
                  ✓ Maximum selected
                </span>
              )}
              {selected.size > 0 && (
                <button
                  onClick={() => setSelected(new Set())}
                  className="text-xs text-gray-400 hover:text-gray-600 underline ml-auto"
                >
                  Clear all
                </button>
              )}
            </div>

            {/* Pending proposals grid */}
            {pendingProposals.length > 0 && (
              <>
                <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
                  Pending ({pendingProposals.length})
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                  {pendingProposals.map((p, i) => (
                    <ProposalCard
                      key={p.id}
                      proposal={p}
                      index={i}
                      selected={selected.has(p.id)}
                      disabled={selected.size >= MAX_SELECT}
                      onToggle={toggleSelect}
                    />
                  ))}
                </div>
              </>
            )}

            {/* Already processed */}
            {otherProposals.length > 0 && (
              <>
                <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  Already Processed ({otherProposals.length})
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-24">
                  {otherProposals.map((p, i) => (
                    <ProposalCard
                      key={p.id}
                      proposal={p}
                      index={pendingProposals.length + i}
                      selected={false}
                      disabled={true}
                      onToggle={() => {}}
                    />
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>

      {/* Sticky bottom action bar */}
      {selected.size > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg z-30">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <div className="text-sm text-gray-600">
              <span className="font-semibold text-gray-900">
                {selected.size} proposals
              </span>{" "}
              selected for approval
            </div>
            <button
              onClick={handleApprove}
              disabled={approving || selected.size === 0}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-semibold px-6 py-2.5 rounded-xl transition-colors flex items-center gap-2"
            >
              {approving ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Approving...
                </>
              ) : (
                `Approve & Generate Selected (${selected.size})`
              )}
            </button>
          </div>
        </div>
      )}

      {/* Generation Progress Modal */}
      {showModal && (
        <GenerationProgressModal
          date={date}
          totalProposals={selected.size}
          onComplete={() => {
            setShowModal(false);
            router.push(`/admin/daily-ca/review/${date}`);
          }}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
}
