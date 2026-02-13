/**
 * CA Chunks Browser Page
 */

'use client';

import { useState } from 'react';
import { useCAChunks } from '@/lib/hooks/use-current-affairs';
import CAChunkCard from '@/components/current-affairs/ca-chunk-card';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Search, LayoutGrid } from 'lucide-react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function CAChunksPage() {
  const [topicId, setTopicId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [includeExpired, setIncludeExpired] = useState(false);
  
  const { data: chunksData, isLoading } = useCAChunks({
    topic_id: topicId || undefined,
    date_from: dateFrom || undefined,
    include_expired: includeExpired,
    ordering: '-published_at',
  });
  
  const chunks = chunksData?.results || [];
  
  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="h-12 w-64 mb-8" />
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-32" />
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
          <LayoutGrid className="h-8 w-8 text-blue-600" />
          <h1 className="text-4xl font-bold">CA Chunks</h1>
        </div>
        <p className="text-gray-600">
          Browse processed current affairs chunks linked to topics
        </p>
      </div>
      
      {/* Filters */}
      <div className="mb-6 bg-gray-50 rounded-lg p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="topic-id">Filter by Topic ID</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                id="topic-id"
                placeholder="Enter topic UUID..."
                value={topicId}
                onChange={(e) => setTopicId(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>
          
          <div>
            <Label htmlFor="date-from">From Date</Label>
            <Input
              id="date-from"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="include-expired"
            checked={includeExpired}
            onChange={(e) => setIncludeExpired(e.target.checked)}
            className="rounded"
          />
          <Label htmlFor="include-expired" className="cursor-pointer">
            Include expired chunks
          </Label>
        </div>
      </div>
      
      {/* Stats */}
      <div className="mb-6 flex items-center justify-between">
        <div className="text-sm text-gray-600">
          Showing {chunks.length} of {chunksData?.count || 0} chunks
        </div>
        
        {dateFrom && (
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setDateFrom('')}
          >
            Clear Date Filter
          </Button>
        )}
      </div>
      
      {/* Chunks */}
      {chunks.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <LayoutGrid className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">No chunks found</p>
          <p className="text-sm text-gray-500 mt-2">
            Try adjusting your filters
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {chunks.map((chunk) => (
            <CAChunkCard key={chunk.id} chunk={chunk} />
          ))}
        </div>
      )}
    </div>
  );
}
