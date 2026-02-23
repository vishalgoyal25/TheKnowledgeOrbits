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

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TheKnowledgeOrbits - AI-Powered UPSC Preparation",
  description:
    "Master UPSC CSE with AI-generated articles and intelligent learning paths",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className} suppressHydrationWarning>
        <GlobalErrorBoundary>
          <QueryProvider>
            <AuthProvider>
              <SidebarProvider>
                <div className="min-h-screen flex flex-col">
                  <Header />
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
