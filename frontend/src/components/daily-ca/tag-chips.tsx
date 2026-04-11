"use client";

import Link from "next/link";
import { Tag } from "@/lib/api/daily-ca";

/**
 * TagChips — clickable keyword tag chips linking to /tags/[slug].
 * Color-coded by tag_type to help visual scanning.
 */

const TAG_TYPE_COLORS: Record<string, string> = {
  topic: "bg-blue-100 text-blue-700 hover:bg-blue-200",
  subtopic: "bg-sky-100 text-sky-700 hover:bg-sky-200",
  scheme: "bg-green-100 text-green-700 hover:bg-green-200",
  law: "bg-purple-100 text-purple-700 hover:bg-purple-200",
  person: "bg-orange-100 text-orange-700 hover:bg-orange-200",
  place: "bg-teal-100 text-teal-700 hover:bg-teal-200",
  organisation: "bg-indigo-100 text-indigo-700 hover:bg-indigo-200",
  concept: "bg-slate-100 text-slate-700 hover:bg-slate-200",
  event: "bg-amber-100 text-amber-700 hover:bg-amber-200",
  other: "bg-gray-100 text-gray-600 hover:bg-gray-200",
};

interface Props {
  tags: Tag[];
  className?: string;
}

export function TagChips({ tags, className = "" }: Props) {
  if (tags.length === 0) return null;

  return (
    <div className={`flex flex-wrap gap-1.5 ${className}`}>
      {tags.map((tag) => {
        const color = TAG_TYPE_COLORS[tag.tag_type] ?? TAG_TYPE_COLORS.other;
        return (
          <Link
            key={tag.id}
            href={`/tags/${tag.slug}`}
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${color}`}
          >
            <span className="opacity-60">#</span>
            {tag.name}
          </Link>
        );
      })}
    </div>
  );
}
