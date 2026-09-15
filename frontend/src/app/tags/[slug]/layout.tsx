import type { Metadata } from "next";
import type { ReactNode } from "react";

import { NOINDEX } from "@/lib/seo/metadata";

// G3.6 — tag pages are client-fetched shells today (Google receives no
// content), and they are not in the sitemap. noindex until they are
// server-rendered like the concept pages were (a later item, not G3's).
export const metadata: Metadata = { title: "Tag", ...NOINDEX };

export default function TagLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
