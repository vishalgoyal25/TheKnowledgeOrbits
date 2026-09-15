import type { Metadata } from "next";
import type { ReactNode } from "react";

import { NOINDEX } from "@/lib/seo/metadata";

// G3.6 — a logged-in tool that costs an LLM call: never in the index.
export const metadata: Metadata = { title: "Generate Article", ...NOINDEX };

export default function GenerateLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
