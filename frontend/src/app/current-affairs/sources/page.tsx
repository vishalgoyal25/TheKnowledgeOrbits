/**
 * CA Sources Status Page
 */

'use client';

import { useCASources } from '@/lib/hooks/use-current-affairs';
import CASourceStatus from '@/components/current-affairs/ca-source-status';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Settings, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

export default function CASourcesPage() {
  const { data: sourcesData, isLoading } = useCASources();
  
  const sources = sourcesData?.results || [];
  
  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="h-12 w-64 mb-8" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      </div>
    );
  }
  
  return (
    <div className="container mx-auto px-4 py-8">
      {/* Back button */}
      <Link href="/current-affairs">
        <Button variant="ghost" className="mb-6 gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Current Affairs
        </Button>
      </Link>
      
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Settings className="h-8 w-8 text-blue-600" />
          <h1 className="text-4xl font-bold">CA Sources</h1>
        </div>
        <p className="text-gray-600">
          Monitor RSS feed sources and scraping status
        </p>
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-blue-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Total Sources</div>
          <div className="text-3xl font-bold text-blue-600">{sources.length}</div>
        </div>
        
        <div className="bg-green-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Active</div>
          <div className="text-3xl font-bold text-green-600">
            {sources.filter(s => s.is_active).length}
          </div>
        </div>
        
        <div className="bg-purple-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">Total Articles</div>
          <div className="text-3xl font-bold text-purple-600">
            {sources.reduce((sum, s) => sum + s.article_count, 0)}
          </div>
        </div>
      </div>
      
      {/* Sources */}
      {sources.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <Settings className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">No sources configured</p>
        </div>
      ) : (
        <CASourceStatus sources={sources} />
      )}
    </div>
  );
}
