"use client";

import Link from "next/link";
import { ConceptLink } from "@/lib/api/daily-ca";

/**
 * ConceptCard — mini card for a ConceptPage link.
 * Shown in the right panel "Concepts Mentioned" section.
 */

interface Props {
  concept: ConceptLink;
}

export function ConceptCard({ concept }: Props) {
  return (
    <Link
      href={`/concepts/${concept.slug}`}
      className="block rounded-xl border border-purple-100 bg-white p-3 hover:border-purple-300 hover:shadow-sm transition-all"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-900 leading-snug line-clamp-2">
            {concept.name}
          </p>
          {concept.brief_description && (
            <p className="mt-1 text-xs text-gray-500 leading-relaxed line-clamp-2">
              {concept.brief_description}
            </p>
          )}
        </div>
        <span
          className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
            concept.is_content_ready
              ? "bg-green-100 text-green-700"
              : "bg-gray-100 text-gray-500"
          }`}
        >
          {concept.is_content_ready ? "Full" : "Stub"}
        </span>
      </div>
    </Link>
  );
}
