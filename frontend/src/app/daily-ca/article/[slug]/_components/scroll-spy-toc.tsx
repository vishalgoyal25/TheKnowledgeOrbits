"use client";

/**
 * P3.1 — ScrollSpyToC
 * Extracted client component: IntersectionObserver + ToC highlight.
 * Receives pre-computed headings from the server component as props.
 * Zero fetch, zero data loading — purely interactive.
 */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

export interface Heading {
  text: string;
  id: string;
}

export function ScrollSpyToC({ headings }: { headings: Heading[] }) {
  const [activeId, setActiveId] = useState("");
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    observerRef.current?.disconnect();

    observerRef.current = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible.length > 0) setActiveId(visible[0].target.id);
      },
      { threshold: 0.3, rootMargin: "-80px 0px -60% 0px" },
    );

    document
      .querySelectorAll("h2[id]")
      .forEach((el) => observerRef.current?.observe(el));

    return () => observerRef.current?.disconnect();
  }, [headings]);

  const handleClick = (id: string) => {
    setActiveId(id);
    document
      .getElementById(id)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <aside className="flex flex-col gap-4">
      {/* Back link */}
      <Link
        href="/daily-ca"
        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-600 transition-colors"
      >
        ← Back to Feed
      </Link>

      {headings.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              In this Article
            </p>
          </div>
          <nav className="py-1.5">
            {headings.map((h) => (
              <button
                key={h.id}
                onClick={() => handleClick(h.id)}
                className={`w-full text-left px-4 py-2 text-xs leading-snug transition-colors border-l-2 ${
                  activeId === h.id
                    ? "border-blue-500 bg-blue-50 text-blue-700 font-medium"
                    : "border-transparent text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
              >
                {h.text}
              </button>
            ))}
          </nav>
        </div>
      )}
    </aside>
  );
}
