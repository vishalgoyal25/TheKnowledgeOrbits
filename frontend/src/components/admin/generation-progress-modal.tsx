"use client";

import { useEffect, useRef, useState } from "react";
import {
  getGenerateStatus,
  GenerateStatusResponse,
} from "@/lib/api/daily-ca-admin";

interface Props {
  date: string;
  totalProposals: number;
  onComplete: () => void;
  onClose: () => void;
}

export function GenerationProgressModal({
  date,
  totalProposals,
  onComplete,
  onClose,
}: Props) {
  const [status, setStatus] = useState<GenerateStatusResponse | null>(null);
  const [done, setDone] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const s = await getGenerateStatus(date);
        setStatus(s);
        if (
          s.generation_complete ||
          s.articles_generated +
            (s.status_breakdown["failed"] || 0) +
            (s.status_breakdown["queued_next_run"] || 0) >=
            totalProposals
        ) {
          setDone(true);
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch {
        // keep polling
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 4000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [date, totalProposals]);

  const generated = status?.status_breakdown["generated"] || 0;
  const failed = status?.status_breakdown["failed"] || 0;
  const queued = status?.status_breakdown["queued_next_run"] || 0;
  const approved = status?.status_breakdown["approved"] || 0;
  const total = status?.total || totalProposals;
  const pct =
    total > 0 ? Math.round(((generated + failed + queued) / total) * 100) : 0;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-gray-900">
            {done ? "Generation Complete" : "Generating Articles..."}
          </h2>
          {done && (
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-xl leading-none"
            >
              ×
            </button>
          )}
        </div>

        {/* Progress bar */}
        <div className="mb-4">
          <div className="flex justify-between text-sm text-gray-500 mb-1">
            <span>
              {generated + failed + queued}/{total} processed
            </span>
            <span>{pct}%</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-3">
            <div
              className={`h-3 rounded-full transition-all duration-500 ${
                done ? "bg-green-500" : "bg-blue-500 animate-pulse"
              }`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Status breakdown */}
        <div className="grid grid-cols-2 gap-2 mb-4 text-sm">
          <div className="bg-green-50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-green-600">{generated}</div>
            <div className="text-xs text-green-700">Generated</div>
          </div>
          <div className="bg-yellow-50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-yellow-600">{approved}</div>
            <div className="text-xs text-yellow-700">Pending</div>
          </div>
          <div className="bg-red-50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-red-600">{failed}</div>
            <div className="text-xs text-red-700">Failed</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-gray-600">{queued}</div>
            <div className="text-xs text-gray-600">Queued Next</div>
          </div>
        </div>

        {/* Hint */}
        {!done && (
          <p className="text-xs text-gray-400 text-center mb-4">
            Generation runs via management command. This page polls for status
            every 4 seconds.
          </p>
        )}

        {/* Actions */}
        {done ? (
          <button
            onClick={onComplete}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-xl transition-colors"
          >
            Review & Publish Articles →
          </button>
        ) : (
          <button
            onClick={onClose}
            className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-2.5 rounded-xl transition-colors text-sm"
          >
            Close (generation continues in background)
          </button>
        )}
      </div>
    </div>
  );
}
