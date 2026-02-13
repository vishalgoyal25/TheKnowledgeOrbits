/**
 * Current Affairs Home Page
 */

'use client';

import { useState } from 'react';
import { useCAArticles, useCASources } from '@/lib/hooks/use-current-affairs';
import CAArticleCard from '@/components/current-affairs/ca-article-card';
import CATimeline from '@/components/current-affairs/ca-timeline';
import CAFilterBar from '@/components/current-affairs/ca-filter-bar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Newspaper, LayoutGrid, History, Settings } from 'lucide-react';
import Link from 'next/link';

export default function CurrentAffairsPage() {
  const [filters, setFilters] = useState({});

  const { data: articlesData, isLoading } = useCAArticles({
    ...filters,
    ordering: '-published_at',
  });

  const { data: sourcesData } = useCASources();

  const articles = articlesData?.results || [];
  const sources = sourcesData?.results || [];

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="h-12 w-64 mb-8" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <Newspaper className="h-8 w-8 text-blue-600" />
            <h1 className="text-4xl font-bold">Current Affairs</h1>
          </div>

          <div className="flex items-center gap-2">
            <Link href="/current-affairs/chunks">
              <Button variant="outline" className="gap-2">
                <LayoutGrid className="h-4 w-4" />
                View Chunks
              </Button>
            </Link>

            <Link href="/current-affairs/sources">
              <Button variant="outline" className="gap-2">
                <Settings className="h-4 w-4" />
                Sources
              </Button>
            </Link>
          </div>
        </div>

        <p className="text-gray-600">
          Stay updated with latest news integrated into UPSC preparation
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-blue-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Total Articles</div>
          <div className="text-3xl font-bold text-blue-600">{articlesData?.count || 0}</div>
        </div>

        <div className="bg-green-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Active Sources</div>
          <div className="text-3xl font-bold text-green-600">
            {sources.filter(s => s.is_active).length}
          </div>
        </div>

        <div className="bg-purple-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Showing</div>
          <div className="text-3xl font-bold text-purple-600">{articles.length}</div>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-8">
        <CAFilterBar
          onFilterChange={setFilters}
          sources={sources.map(s => ({ id: s.id, name: s.name }))}
        />
      </div>

      {/* Views */}
      <Tabs defaultValue="grid" className="w-full">
        <TabsList>
          <TabsTrigger value="grid" className="gap-2">
            <LayoutGrid className="h-4 w-4" />
            Grid
          </TabsTrigger>
          <TabsTrigger value="timeline" className="gap-2">
            <History className="h-4 w-4" />
            Timeline
          </TabsTrigger>
        </TabsList>

        <TabsContent value="grid" className="mt-6">
          {articles.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <Newspaper className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">No articles found</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {articles.map((article) => (
                <CAArticleCard key={article.id} article={article} />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="timeline" className="mt-6">
          {articles.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <History className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">No articles found</p>
            </div>
          ) : (
            <CATimeline articles={articles} />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
