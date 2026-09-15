import type { ReactNode } from "react";

import { buildMetadata } from "@/lib/seo/metadata";

// G3.4 — the page is a client component; its metadata lives here.
export const metadata = buildMetadata({
  title: "Current Affairs Sources",
  description:
    "The official and reputed publications TheKnowledgeOrbits draws current affairs from for UPSC preparation.",
  path: "/current-affairs/sources",
});

export default function SourcesLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
