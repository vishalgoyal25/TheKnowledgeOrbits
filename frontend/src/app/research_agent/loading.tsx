// Automatic Next.js loading UI — shown by the router during navigation to /research_agent
// before the page component has mounted. No logic, no API calls, pure skeleton.

export default function ResearchAgentLoading() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 animate-pulse">
      {/* Page heading skeleton */}
      <div className="mb-6 space-y-2">
        <div className="h-7 w-56 rounded-lg bg-gray-200" />
        <div className="h-4 w-96 rounded bg-gray-100" />
      </div>

      {/* Input box skeleton */}
      <div className="mb-8 h-28 w-full rounded-xl border border-gray-200 bg-gray-50" />

      {/* Two-column layout skeleton (graph left, report right) */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Graph panel */}
        <div className="flex flex-col gap-3">
          <div className="h-4 w-24 rounded bg-gray-200" />
          <div className="h-[520px] w-full rounded-xl border border-gray-100 bg-gray-50" />
        </div>

        {/* Report panel */}
        <div className="flex flex-col gap-4">
          <div className="h-4 w-32 rounded bg-gray-200" />
          <div className="space-y-3">
            {[90, 100, 75, 95, 60, 85, 100, 70].map((w, i) => (
              <div
                key={i}
                className="h-3 rounded bg-gray-100"
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
