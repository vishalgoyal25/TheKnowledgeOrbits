import type { Metadata } from "next";
import type { ReactNode } from "react";

import { NOINDEX } from "@/lib/seo/metadata";

// G3.6 — login, register, reset, verify: never in the index.
export const metadata: Metadata = { title: "Account", ...NOINDEX };

export default function AuthLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
