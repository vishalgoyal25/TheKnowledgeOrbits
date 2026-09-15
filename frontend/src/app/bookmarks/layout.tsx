import type { Metadata } from "next";
import type { ReactNode } from "react";

import { NOINDEX } from "@/lib/seo/metadata";

// G3.6 — per-user surface: never in the index.
export const metadata: Metadata = { title: "Bookmarks", ...NOINDEX };

export default function BookmarksLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
