import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SSEProvider } from "@/components/research_agent/SSEProvider";

export const metadata: Metadata = {
  title: "Research Agent — TheKnowledgeOrbits",
  description:
    "AI-powered deep research for UPSC preparation. Ask any question — get a structured, cited report in minutes.",
  robots: { index: false, follow: false }, // research pages are user-specific, not for SEO
};

export default function ResearchAgentLayout({
  children,
}: {
  children: ReactNode;
}) {
  // SSEProvider wraps ALL /research_agent/* pages.
  // The single SSE connection lives here — it persists across sub-page navigations
  // (history list → detail page) without breaking or reopening.
  return <SSEProvider>{children}</SSEProvider>;
}
