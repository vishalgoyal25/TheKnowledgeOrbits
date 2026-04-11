"use client";

/**
 * ConceptStubCard — shown when is_content_ready=False.
 * Displays a "Full article in progress" banner with the brief description.
 */

interface Props {
  name: string;
  briefDescription: string;
}

export function ConceptStubCard({ name, briefDescription }: Props) {
  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 overflow-hidden">
      {/* Banner */}
      <div className="flex items-center gap-2 bg-amber-100 px-4 py-2.5">
        <span className="text-base" aria-hidden="true">
          🚧
        </span>
        <p className="text-xs font-semibold text-amber-800">
          Full article in progress. Check back soon.
        </p>
      </div>

      {/* Brief description */}
      <div className="px-5 py-4">
        <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-2">
          About — {name}
        </p>
        {briefDescription ? (
          <p className="text-sm text-amber-900 leading-relaxed">
            {briefDescription}
          </p>
        ) : (
          <p className="text-sm text-amber-600 italic">
            This concept was identified during article generation. A full
            explanation will be added soon.
          </p>
        )}
      </div>
    </div>
  );
}
