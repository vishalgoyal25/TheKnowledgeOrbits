import type { Metadata } from "next";
import type { ReactNode } from "react";

import { NOINDEX } from "@/lib/seo/metadata";

// G3.6 — an operational status page, not content.
export const metadata: Metadata = { title: "Status", ...NOINDEX };

export default function HealthLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
