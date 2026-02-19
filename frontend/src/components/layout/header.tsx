/**
 * Enhanced header with search bar
 */

'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { BookOpen, FileText, Folder, Sparkles, Search, LayoutDashboard, Newspaper, BookMarked, Bookmark, FileQuestion } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth/useAuth';
import UserMenu from '@/components/auth/UserMenu';
import { useSearch } from '@/lib/hooks/use-search';

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [isFocused, setIsFocused] = useState(false);

  // Use debounced search query
  const [debouncedQuery, setDebouncedQuery] = useState('');

  // Debounce logic
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch results using our new hook
  const { data: searchResults, isLoading: isSearching } = useSearch(
    { q: debouncedQuery, limit: 5 },
    debouncedQuery.length >= 2
  );

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      setIsFocused(false);
      router.push(`/search?q=${encodeURIComponent(searchQuery)}`);
    }
  };

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

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/60">
      {/* LAYER 1: TOP BAR (Brand, Search, Utility) */}
      <div className="border-b bg-white/50 relative z-50">
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
            <div className="flex-1 max-w-xl hidden md:block relative">
              <form onSubmit={handleSearchSubmit} className="relative group">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 group-focus-within:text-blue-600 transition-colors pointer-events-none" />
                <Input
                  type="search"
                  placeholder="Ask anything about UPSC Syllabus..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setTimeout(() => setIsFocused(false), 200)} // Delay to allow click
                  className="pl-10 pr-4 h-11 bg-slate-50 border-slate-200 focus:bg-white focus:ring-2 focus:ring-blue-100 transition-all rounded-xl w-full"
                />
              </form>

              {/* SMART DROPDOWN RESULTS */}
              {isFocused && (searchQuery.length >= 2) && (
                <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-2xl shadow-xl border border-slate-100 overflow-hidden max-h-[80vh] overflow-y-auto animate-in fade-in slide-in-from-top-2">
                  {isSearching ? (
                    <div className="p-4 text-center text-sm text-slate-500 flex items-center justify-center gap-2">
                      <Sparkles className="h-4 w-4 animate-spin text-blue-500" /> Thinking...
                    </div>
                  ) : searchResults && searchResults.length > 0 ? (
                    <div className="py-2">
                      <div className="px-4 py-2 text-xs font-bold text-slate-400 uppercase tracking-wider">Top Results</div>
                      {searchResults.map((result: any) => (
                        <Link
                          key={result.id}
                          href={result.url || '#'}
                          className="block px-4 py-3 hover:bg-slate-50 transition-colors border-b border-slate-50 last:border-0"
                        >
                          <div className="flex items-start gap-3">
                            <div className={cn(
                              "h-8 w-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5",
                              result.type === 'topic' ? "bg-purple-100 text-purple-600" :
                                result.type === 'current_affair' ? "bg-emerald-100 text-emerald-600" :
                                  "bg-blue-100 text-blue-600"
                            )}>
                              {result.type === 'topic' ? <Folder className="h-4 w-4" /> :
                                result.type === 'current_affair' ? <Newspaper className="h-4 w-4" /> :
                                  <FileText className="h-4 w-4" />}
                            </div>
                            <div>
                              <h4 className="text-sm font-bold text-slate-900 line-clamp-1">{result.title}</h4>
                              <p className="text-xs text-slate-500 line-clamp-1 mt-0.5">{result.snippet}</p>
                              <div className="flex gap-2 mt-1.5">
                                {result.metadata?.subject && (
                                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                                    {result.metadata.subject}
                                  </span>
                                )}
                                {result.metadata?.date && (
                                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                                    {result.metadata.date}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        </Link>
                      ))}
                      <Link href={`/search?q=${encodeURIComponent(searchQuery)}`} className="block p-3 text-center text-sm font-bold text-blue-600 hover:bg-blue-50 transition-colors border-t border-slate-100">
                        View all results
                      </Link>
                    </div>
                  ) : (
                    <div className="p-8 text-center">
                      <p className="text-slate-500 text-sm">No orbits found for "{searchQuery}"</p>
                    </div>
                  )}
                </div>
              )}
            </div>

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
      <div className="bg-white border-b relative z-40 shadow-sm">
        <div className="container mx-auto px-4">
          <nav className="flex items-center h-12 overflow-x-auto no-scrollbar gap-2 scroll-smooth">
            {navItems.filter(item => !item.protected || isAuthenticated).map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center space-x-2 px-4 h-full text-sm font-bold transition-all border-b-2 whitespace-nowrap shrink-0 group',
                    isActive
                      ? 'text-blue-600 border-blue-600 bg-blue-50/50'
                      : 'text-slate-500 border-transparent hover:text-slate-900 hover:bg-slate-50'
                  )}
                >
                  <Icon className={cn("h-4 w-4 transition-transform group-hover:scale-110", isActive ? "text-blue-600" : "text-slate-400")} />
                  <span>{item.label}</span>
                </Link>
              );
            })}

            {/* Future Scaling Space */}
            <div className="ml-auto flex items-center gap-2 pl-4 border-l border-slate-100 hidden lg:flex">
              <span className="text-[10px] font-black text-slate-300 uppercase tracking-tighter cursor-default select-none">
                More Modules Loading...
              </span>
            </div>
          </nav>
        </div>
      </div>
    </header>
  );
}
