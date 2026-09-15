/**
 * Dashboard Layout
 */

import type { Metadata } from "next";
import React from "react";

import { NOINDEX } from "@/lib/seo/metadata";

// G3.6 — per-user surface: never in the index.
export const metadata: Metadata = { title: "Dashboard", ...NOINDEX };

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
