/**
 * Enhanced Dashboard Sidebar - Comprehensive navigation for UPSC preparation
 */

"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Folder,
  Sparkles,
  Newspaper,
  BookMarked,
  Bookmark,
  History,
  Settings,
  ChevronLeft,
  ChevronRight,
  Zap,
  LifeBuoy,
  FileQuestion,
  LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useAuth } from "@/lib/auth/useAuth";
import { useSidebar } from "@/components/providers/sidebar-provider";

/**
 * Interface for navigation items in the sidebar.
 */
interface NavItem {
  /** The text displayed in the sidebar. */
  title: string;
  /** The destination route. */
  href: string;
  /** The Lucide icon component to render. */
  icon: LucideIcon;
  /** UI variant for the button. */
  variant: "ghost" | "default";
  /** Grouping category for organization. */
  category: "primary" | "secondary" | "tools";
}

const navItems: NavItem[] = [
  {
    title: "Overview",
    href: "/dashboard",
    icon: LayoutDashboard,
    variant: "default",
    category: "primary",
  },
  {
    title: "My Notebook",
    href: "/notebook",
    icon: BookMarked,
    variant: "ghost",
    category: "primary",
  },
  {
    title: "Bookmarks",
    href: "/bookmarks",
    icon: Bookmark,
    variant: "ghost",
    category: "primary",
  },
  {
    title: "Reading History",
    href: "/articles/history",
    icon: History,
    variant: "ghost",
    category: "primary",
  },

  {
    title: "Quizzes",
    href: "/assessment",
    icon: FileQuestion,
    variant: "ghost",
    category: "tools",
  },
  {
    title: "Quiz History",
    href: "/assessment/history",
    icon: History,
    variant: "ghost",
    category: "tools",
  },
  {
    title: "Generate AI Article",
    href: "/generate",
    icon: Sparkles,
    variant: "ghost",
    category: "tools",
  },
  {
    title: "Browse Topics",
    href: "/topics",
    icon: Folder,
    variant: "ghost",
    category: "tools",
  },
  {
    title: "News",
    href: "/news",
    icon: Newspaper,
    variant: "ghost",
    category: "tools",
  },

  {
    title: "Settings",
    href: "/settings",
    icon: Settings,
    variant: "ghost",
    category: "secondary",
  },
  {
    title: "Help & Support",
    href: "/support",
    icon: LifeBuoy,
    variant: "ghost",
    category: "secondary",
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { isCollapsed, toggleSidebar } = useSidebar();
  const { user, isAuthenticated: _isAuthenticated } = useAuth();

  const NavLink = ({ item }: { item: NavItem }) => {
    const Icon = item.icon;
    const isActive = pathname === item.href;

    return (
      <Link href={item.href}>
        <div
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 group relative",
            isActive
              ? "bg-blue-600 text-white shadow-md shadow-blue-200"
              : "text-gray-600 hover:bg-blue-50 hover:text-blue-600",
          )}
        >
          <Icon
            className={cn(
              "h-5 w-5 flex-shrink-0",
              isActive
                ? "text-white"
                : "group-hover:scale-110 transition-transform",
            )}
          />
          {!isCollapsed && (
            <span className="font-medium text-sm truncate">{item.title}</span>
          )}

          {isCollapsed && (
            <div className="absolute right-14 bg-gray-900 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
              {item.title}
            </div>
          )}
        </div>
      </Link>
    );
  };

  return (
    <aside
      className={cn(
        "absolute right-0 top-0 flex flex-col bg-white transition-all duration-300 ease-in-out z-40 h-[calc(100vh-112px)] overflow-hidden",
        isCollapsed ? "w-0 border-l-0" : "w-64 border-l",
      )}
    >
      {/* Collapse Toggle */}
      <Button
        variant="default"
        size="icon"
        className={cn(
          "fixed top-[170px] h-10 w-10 rounded-l-xl rounded-r-none border-r-0 shadow-[theme(colors.blue.300/30)_0_4px_12px_-2px] bg-blue-600 hover:bg-blue-700 text-white z-50 transition-all duration-300 ease-in-out",
          isCollapsed ? "right-0" : "right-64",
        )}
        onClick={toggleSidebar}
        suppressHydrationWarning
      >
        {isCollapsed ? (
          <ChevronLeft className="h-5 w-5" />
        ) : (
          <ChevronRight className="h-5 w-5" />
        )}
      </Button>

      <div
        className={cn(
          "flex flex-col h-full transition-opacity duration-200",
          isCollapsed ? "opacity-0 pointer-events-none" : "opacity-100",
        )}
      >
        <ScrollArea className="flex-1 px-3 py-6">
          <div className="space-y-8">
            {/* Section: Learning */}
            <div className="space-y-2">
              {!isCollapsed && (
                <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-gray-400">
                  Main Menu
                </p>
              )}
              <div className="space-y-1">
                {navItems
                  .filter((i) => i.category === "primary")
                  .map((item) => (
                    <NavLink key={item.href} item={item} />
                  ))}
              </div>
            </div>

            {/* Section: Tools */}
            <div className="space-y-2">
              {!isCollapsed && (
                <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-gray-400">
                  Knowledge Tools
                </p>
              )}
              <div className="space-y-1">
                {navItems
                  .filter((i) => i.category === "tools")
                  .map((item) => (
                    <NavLink key={item.href} item={item} />
                  ))}
              </div>
            </div>

            {/* Upgrade Card / Tip */}
            {!isCollapsed && (
              <div className="mx-2 p-4 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-xl text-white space-y-3 shadow-inner">
                <div className="flex items-center gap-2">
                  <Zap className="h-4 w-4 text-yellow-400 fill-yellow-400" />
                  <span className="text-xs font-bold">Pro Tip</span>
                </div>
                <p className="text-[10px] leading-relaxed opacity-90">
                  Regular quiz attempts increase syllabus retention by up to
                  45%. Try our daily orbits!
                </p>
                <Link href="/assessment/generate">
                  <Button
                    size="sm"
                    className="w-full bg-white/20 hover:bg-white/30 text-white border-none text-[10px] h-7"
                  >
                    Take Quiz
                  </Button>
                </Link>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* User Footer Section */}
        <div className="p-4 border-t bg-gray-50/50">
          <div
            className={cn(
              "flex items-center gap-3",
              isCollapsed ? "justify-center" : "",
            )}
          >
            <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 font-bold border border-blue-200">
              {user?.full_name?.charAt(0) || "U"}
            </div>
            {!isCollapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-gray-900 truncate">
                  {user?.full_name || "Guest Student"}
                </p>
                <p className="text-[10px] text-gray-500 truncate">
                  {user?.email || "Aspirant"}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}
