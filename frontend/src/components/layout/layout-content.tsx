"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { useSidebar } from "@/components/providers/sidebar-provider";
import { cn } from "@/lib/utils";
import Sidebar from "@/components/layout/sidebar";
import Footer from "@/components/layout/footer";

export function LayoutContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { isCollapsed } = useSidebar();

  // On the homepage, we don't apply global padding here
  // because the homepage handles its own selective padding for the Hero section.
  const isHomePage = pathname === "/";

  // NOTE: <main> deliberately has NO `overflow-y-auto`. The outer wrapper uses
  // `min-h-screen` (not `h-screen`), so <main> has no bounded height and the
  // WINDOW is the real scroll container. An `overflow-y-auto` here would create
  // a CSS scroll container that never actually scrolls — silently breaking
  // `position: sticky` for any descendant (it would resolve against this dead
  // scrollport instead of the window). Keep the window as the scrollport.
  return (
    <main className="flex-1 bg-gray-50 flex flex-col scroll-smooth">
      <div className="relative flex flex-1">
        <div
          className={cn(
            "flex-1 min-w-0 transition-all duration-300 ease-in-out",
            !isHomePage && (isCollapsed ? "lg:pr-0" : "lg:pr-64"),
          )}
        >
          {children}
        </div>
        <Sidebar />
      </div>
      <Footer />
    </main>
  );
}
