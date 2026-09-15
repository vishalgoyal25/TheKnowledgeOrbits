import type { Metadata } from "next";
import type { ReactNode } from "react";

import { NOINDEX } from "@/lib/seo/metadata";

// G3.6 — internal search results are infinite, query-dependent and thin as
// crawl targets; Google's own guidance is to keep them out of the index.
export const metadata: Metadata = { title: "Search", ...NOINDEX };

export default function SearchLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
