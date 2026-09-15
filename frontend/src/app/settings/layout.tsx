import type { Metadata } from "next";
import type { ReactNode } from "react";

import { NOINDEX } from "@/lib/seo/metadata";

// G3.6 — per-user surface: never in the index. The page itself is a client
// component, so the robots directive lives on this server layout.
export const metadata: Metadata = { title: "Settings", ...NOINDEX };

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
