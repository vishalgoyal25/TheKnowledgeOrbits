import type { Metadata } from "next";
import type { ReactNode } from "react";

import { NOINDEX } from "@/lib/seo/metadata";

// G3.6 — staff surfaces: never in the index.
export const metadata: Metadata = { title: "Admin", ...NOINDEX };

export default function AdminLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
