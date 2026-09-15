import type { Metadata } from "next";
import type { ReactNode } from "react";

import { NOINDEX } from "@/lib/seo/metadata";

// G3.6 — per-user surface: never in the index.
export const metadata: Metadata = { title: "Profile", ...NOINDEX };

export default function ProfileLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
