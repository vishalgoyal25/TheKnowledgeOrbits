import type { ReactNode } from "react";

import { buildMetadata } from "@/lib/seo/metadata";

// G3.4 — the page is a client component; its metadata lives here.
export const metadata = buildMetadata({
  title: "UPSC News",
  description:
    "Daily news for UPSC aspirants, filtered by category — national, international, economy, science, environment and more.",
  path: "/news",
});

export default function NewsLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
