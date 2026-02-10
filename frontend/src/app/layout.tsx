/**
 * Root layout with providers
 */

import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import '../styles/globals.css';
import { QueryProvider } from '@/components/providers/query-provider';
import Header from '@/components/layout/header';

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
    <html lang="en">
      <body className={inter.className}>
        <QueryProvider>
          <div className="min-h-screen flex flex-col">
            <Header />
            <main className="flex-1">
              {children}
            </main>
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
