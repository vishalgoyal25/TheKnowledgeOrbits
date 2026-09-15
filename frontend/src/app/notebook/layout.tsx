import type { Metadata } from "next";
import type { ReactNode } from "react";

import { NOINDEX } from "@/lib/seo/metadata";

// G3.6 — the user's private articles: never in the index.
export const metadata: Metadata = { title: "My Notebook", ...NOINDEX };

export default function NotebookLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
