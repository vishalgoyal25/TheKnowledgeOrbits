import type { Metadata } from "next";
import ResearchHistory from "@/components/research_agent/ResearchHistory";
import { History } from "lucide-react";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Research History — TheKnowledgeOrbits",
  robots: { index: false, follow: false },
};

export default function ResearchHistoryPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-blue-600 shadow-sm">
            <History className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              Research History
            </h1>
            <p className="text-xs text-gray-500">
              Your past AI research sessions
            </p>
          </div>
        </div>

        <Link
          href="/research_agent"
          className="flex-shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          New Research
        </Link>
      </div>

      {/* History list — auth-gating and pagination handled inside the component */}
      <ResearchHistory />
    </main>
  );
}
