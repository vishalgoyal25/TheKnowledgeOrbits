"use client";

/**
 * OrbitIcon — animated SVG Knowledge Map button.
 *
 * 3 elliptical orbit rings at -60° / 0° / +60° with travelling dots.
 * Hover: each ring group spins at a different speed.
 * Desktop (xl+): icon + "Knowledge Map" label.
 * Below xl: icon only.
 */

import Link from "next/link";
import { cn } from "@/lib/utils";

interface OrbitIconProps {
  className?: string;
  label?: string;
}

export default function OrbitIcon({
  className,
  label = "Knowledge Map",
}: OrbitIconProps) {
  return (
    <Link
      href="/knowledge"
      className={cn(
        "group flex items-center gap-2 px-2 py-1 rounded-lg",
        "text-slate-600 hover:text-blue-600 transition-colors duration-200",
        className,
      )}
      title="Knowledge Map"
    >
      <svg
        width="28"
        height="28"
        viewBox="0 0 28 28"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        className="flex-shrink-0"
      >
        {/*
          Each ring + its dot live in a <g> rotated to its tilt angle.
          The CSS animation on hover overrides the static rotation with a
          full 360° spin — no conflict because the keyframes carry the
          start angle themselves (from -60° → 300°, etc.).
          transform-origin is set inline so it applies correctly in SVG space.
        */}

        {/* ── Ring 1 — tilted -60° ─────────────────────────────────────── */}
        <g
          style={{ transformOrigin: "14px 14px", transform: "rotate(-60deg)" }}
          className="group-hover:[animation:orbit-spin-1_4s_linear_infinite]"
        >
          <ellipse
            cx="14" cy="14" rx="12" ry="4.5"
            stroke="currentColor" strokeWidth="1.2" strokeOpacity="0.85" fill="none"
          />
          {/* dot at right edge of ellipse: cx = 14 + 12 = 26 */}
          <circle cx="26" cy="14" r="1.5" fill="currentColor" fillOpacity="0.9" />
        </g>

        {/* ── Ring 2 — equatorial (0°) ─────────────────────────────────── */}
        <g
          style={{ transformOrigin: "14px 14px", transform: "rotate(0deg)" }}
          className="group-hover:[animation:orbit-spin-2_6s_linear_infinite]"
        >
          <ellipse
            cx="14" cy="14" rx="12" ry="4.5"
            stroke="currentColor" strokeWidth="1.2" strokeOpacity="0.85" fill="none"
          />
          <circle cx="26" cy="14" r="1.5" fill="currentColor" fillOpacity="0.9" />
        </g>

        {/* ── Ring 3 — tilted +60° ─────────────────────────────────────── */}
        <g
          style={{ transformOrigin: "14px 14px", transform: "rotate(60deg)" }}
          className="group-hover:[animation:orbit-spin-3_8s_linear_infinite]"
        >
          <ellipse
            cx="14" cy="14" rx="12" ry="4.5"
            stroke="currentColor" strokeWidth="1.2" strokeOpacity="0.85" fill="none"
          />
          <circle cx="26" cy="14" r="1.5" fill="currentColor" fillOpacity="0.9" />
        </g>

        {/* ── Earth — central dot ───────────────────────────────────────── */}
        <circle
          cx="14" cy="14" r="3.5"
          fill="currentColor" fillOpacity="0.9"
          className="group-hover:fill-blue-500 transition-colors duration-300"
        />
        {/* shimmer ring around Earth */}
        <circle
          cx="14" cy="14" r="5"
          stroke="currentColor" strokeWidth="0.75" strokeOpacity="0.3" fill="none"
        />
      </svg>

      {label && (
        <span className="hidden xl:inline-block font-semibold text-sm whitespace-nowrap">
          {label}
        </span>
      )}
    </Link>
  );
}
