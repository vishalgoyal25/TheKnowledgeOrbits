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
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center justify-between gap-4">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-2 flex-shrink-0">
            <BookOpen className="h-6 w-6 text-blue-600" />
            <span className="text-xl font-bold text-gray-900 hidden sm:inline">
              TheKnowledgeOrbits
            </span>
            <span className="text-xl font-bold text-gray-900 sm:hidden">
              TKO
            </span>
          </Link>

          {/* Search Bar */}
          <form onSubmit={handleSearch} className="flex-1 max-w-md hidden md:block">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                type="search"
                placeholder="Search articles, topics..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 pr-4"
              />
            </div>
          </form>

          {/* Navigation */}
          <div className="flex items-center space-x-4">
            <nav className="hidden lg:flex items-center space-x-1">
              {navItems.filter(item => !item.protected || isAuthenticated).map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.href;

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      'flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors hover:bg-gray-100',
                      isActive ? 'text-blue-600 bg-blue-50' : 'text-gray-600'
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>

            <div className="flex items-center space-x-2 border-l pl-4">
              {!isLoading && (
                isAuthenticated ? (
                  <UserMenu />
                ) : (
                  <>
                    <Button variant="ghost" size="sm" asChild className="hidden sm:inline-flex">
                      <Link href="/auth/login">Login</Link>
                    </Button>
                    <Button size="sm" asChild>
                      <Link href="/auth/register">Sign Up</Link>
                    </Button>
                  </>
                )
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
