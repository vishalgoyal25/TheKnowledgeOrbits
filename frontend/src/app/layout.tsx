/**
 * Root layout with providers
 */
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "../styles/globals.css";
import { QueryProvider } from "@/components/providers/query-provider";
import Header from "@/components/layout/header";
import { Toaster } from "@/components/ui/toaster";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { SidebarProvider } from "@/components/providers/sidebar-provider";
import { LayoutContent } from "@/components/layout/layout-content";
import FeedbackButton from "@/components/support/feedback-button";
import { GlobalErrorBoundary } from "@/components/shared/GlobalErrorBoundary";
import { getHierarchyData } from "@/lib/api/server-hierarchy";
import GoogleAnalytics from "@/components/telemetry/GoogleAnalytics";
import PageViewTracker from "@/components/telemetry/PageViewTracker";
import { SITE_NAME, SITE_URL } from "@/lib/seo/site";

const inter = Inter({ subsets: ["latin"] });

// G3.4 — site-wide defaults. `metadataBase` turns every relative canonical /
// OG URL below and in each page's metadata into an absolute one; `title.template`
// gives every page the brand suffix once, so pages set only their own part.
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "TheKnowledgeOrbits — AI-Powered UPSC Preparation",
    template: "%s | TheKnowledgeOrbits",
  },
  description:
    "Master UPSC CSE with AI-generated articles, daily current affairs and a connected knowledge map of the whole syllabus.",
  applicationName: SITE_NAME,
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    locale: "en_IN",
    url: "/",
    title: "TheKnowledgeOrbits — AI-Powered UPSC Preparation",
    description:
      "AI-generated study articles, daily current affairs and a connected knowledge map of the UPSC CSE syllabus.",
  },
  twitter: {
    card: "summary_large_image",
    title: "TheKnowledgeOrbits — AI-Powered UPSC Preparation",
    description:
      "AI-generated study articles, daily current affairs and a connected knowledge map of the UPSC CSE syllabus.",
  },
  robots: { index: true, follow: true },
  // No root canonical: each page sets its own, so a private page never
  // inherits "/" as its canonical.
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Fetch hierarchy in parallel (server-side). This is cached for 30 min.
  const initialHierarchy = await getHierarchyData();

  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className} suppressHydrationWarning>
        {/*
          Both render null without NEXT_PUBLIC_GA_ID. PageViewTracker carries its
          own <Suspense> boundary internally — do NOT unwrap it or mount its inner
          component directly here: useSearchParams() outside a boundary in this
          file turns every route on the site dynamic (see FEATURES_GROWTH_STACK
          §5.4, R1).
        */}
        <GoogleAnalytics />
        <PageViewTracker />
        <GlobalErrorBoundary>
          <QueryProvider>
            <AuthProvider>
              <SidebarProvider>
                <div className="min-h-screen flex flex-col">
                  {/* Pass the server-baked hierarchy to the Client Header */}
                  <Header initialHierarchy={initialHierarchy} />
                  <LayoutContent>{children}</LayoutContent>
                  <FeedbackButton />
                  <Toaster />
                </div>
              </SidebarProvider>
            </AuthProvider>
          </QueryProvider>
        </GlobalErrorBoundary>
      </body>
    </html>
  );
}
