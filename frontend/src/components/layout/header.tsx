/**
 * Enhanced header with search bar
 */

'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { BookOpen, FileText, Folder, Sparkles, Search, LayoutDashboard, Newspaper, BookMarked, Bookmark, FileQuestion } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth/useAuth';
import UserMenu from '@/components/auth/UserMenu';

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');

  const navItems = [
    { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, protected: false },
    { href: '/articles', label: 'Articles', icon: FileText, protected: false },
    { href: '/topics', label: 'Topics', icon: Folder, protected: false },
    { href: '/assessment', label: 'Quizzes', icon: FileQuestion, protected: false },
    { href: '/generate', label: 'Generate', icon: Sparkles, protected: false },
    { href: '/current-affairs', label: 'Current Affairs', icon: Newspaper, protected: false },
    { href: '/notebook', label: 'My Notebook', icon: BookMarked, protected: true },
    { href: '/bookmarks', label: 'Bookmarks', icon: Bookmark, protected: true },
  ];

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/search?q=${encodeURIComponent(searchQuery)}`);
    }
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/60">
      {/* LAYER 1: TOP BAR (Brand, Search, Utility) */}
      <div className="border-b bg-white/50">
        <div className="container mx-auto px-4">
          <div className="flex h-16 items-center justify-between gap-8">
            {/* Logo */}
            <Link href="/" className="flex items-center space-x-2 flex-shrink-0">
              <BookOpen className="h-7 w-7 text-blue-600" />
              <div className="flex flex-col">
                <span className="text-xl font-black text-slate-900 tracking-tight leading-none">
                  TheKnowledgeOrbits
                </span>
                <span className="text-[10px] font-bold text-blue-600 uppercase tracking-widest mt-1">
                  AI-Powered UPSC OS
                </span>
              </div>
            </Link>

            {/* Central Search Bar (Professional Global Command) */}
            <form onSubmit={handleSearch} className="flex-1 max-w-xl hidden md:block">
              <div className="relative group">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 group-focus-within:text-blue-600 transition-colors" />
                <Input
                  type="search"
                  placeholder="Ask anything about UPSC Syllabus..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-4 h-11 bg-slate-50 border-slate-200 focus:bg-white focus:ring-2 focus:ring-blue-100 transition-all rounded-xl"
                />
              </div>
            </form>

            {/* Top Right Utility */}
            <div className="flex items-center gap-6">
              <nav className="hidden xl:flex items-center gap-6 text-sm font-semibold text-slate-600">
                <Link href="/" className="hover:text-blue-600 transition-colors">Home</Link>
                <Link href="/about" className="hover:text-blue-600 transition-colors">About</Link>
                <Link href="/contact" className="hover:text-blue-600 transition-colors">Contact Us</Link>
              </nav>

              <div className="flex items-center space-x-2 border-l pl-6 border-slate-200 h-8">
                {!isLoading && (
                  isAuthenticated ? (
                    <UserMenu />
                  ) : (
                    <>
                      <Button variant="ghost" size="sm" asChild className="hidden sm:inline-flex font-bold">
                        <Link href="/auth/login">Login</Link>
                      </Button>
                      <Button size="sm" asChild className="bg-blue-600 hover:bg-blue-700 font-bold shadow-md shadow-blue-200">
                        <Link href="/auth/register">Join Pro</Link>
                      </Button>
                    </>
                  )
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* LAYER 2: FEATURE BAR (Horizontal Navigation) */}
      <div className="bg-white">
        <div className="container mx-auto px-4">
          <nav className="flex items-center h-12 overflow-x-auto no-scrollbar gap-2 scroll-smooth">
            {navItems.filter(item => !item.protected || isAuthenticated).map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center space-x-2 px-4 h-full text-sm font-bold transition-all border-b-2 whitespace-nowrap shrink-0',
                    isActive
                      ? 'text-blue-600 border-blue-600 bg-blue-50/50'
                      : 'text-slate-500 border-transparent hover:text-slate-900 hover:bg-slate-50'
                  )}
                >
                  <Icon className={cn("h-4 w-4", isActive ? "text-blue-600" : "text-slate-400")} />
                  <span>{item.label}</span>
                </Link>
              );
            })}

            {/* Future Scaling Space */}
            <div className="ml-auto flex items-center gap-2 pl-4 border-l border-slate-100 hidden lg:flex">
              <span className="text-[10px] font-black text-slate-300 uppercase tracking-tighter">New Sections Coming Soon</span>
            </div>
          </nav>
        </div>
      </div>
    </header>
  );
}
