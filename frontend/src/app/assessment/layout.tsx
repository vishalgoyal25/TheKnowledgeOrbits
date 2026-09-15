import type { Metadata } from "next";
import type { ReactNode } from "react";

import { NOINDEX } from "@/lib/seo/metadata";

// G3.6 — quizzes and per-user results: never in the index.
export const metadata: Metadata = { title: "Assessment", ...NOINDEX };

export default function AssessmentLayout({
  children,
}: {
  children: ReactNode;
}) {
  return <>{children}</>;
}
