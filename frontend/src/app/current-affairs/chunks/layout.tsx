import type { ReactNode } from "react";

import { buildMetadata } from "@/lib/seo/metadata";

// G3.4 — the page is a client component; its metadata lives here.
export const metadata = buildMetadata({
  title: "Current Affairs Chunks",
  description:
    "Current-affairs passages linked to UPSC syllabus topics — the raw material behind the generated study articles.",
  path: "/current-affairs/chunks",
});

export default function ChunksLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
