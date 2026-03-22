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

  return (
    <main className="flex-1 overflow-y-auto bg-gray-50 flex flex-col scroll-smooth">
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
