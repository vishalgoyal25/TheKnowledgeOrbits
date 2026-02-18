/**
 * Root layout with providers
 */
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import '../styles/globals.css';
import { QueryProvider } from '@/components/providers/query-provider';
import Header from '@/components/layout/header';
import Footer from '@/components/layout/footer';
import Sidebar from '@/components/layout/sidebar';
import { Toaster } from '@/components/ui/toaster';
import { AuthProvider } from '@/lib/auth/AuthProvider';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'TheKnowledgeOrbits - AI-Powered UPSC Preparation',
  description: 'Master UPSC CSE with AI-generated articles and intelligent learning paths',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className} suppressHydrationWarning>
        <QueryProvider>
          <AuthProvider>
            <div className="min-h-screen flex flex-col">
              <Header />
              <div className="flex flex-1 overflow-hidden">
                <Sidebar />
                <main className="flex-1 overflow-y-auto bg-gray-50 flex flex-col">
                  <div className="flex-1">
                    {children}
                  </div>
                  <Footer />
                </main>
              </div>
              <Toaster />
            </div>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
