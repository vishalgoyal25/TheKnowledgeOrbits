/**
 * Search results page
 */

'use client';

import { useSearchParams } from 'next/navigation';
import { useSearch } from '@/lib/hooks/use-search';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Search, FileText, Folder, AlertCircle } from 'lucide-react';

export default function SearchPage() {
  const searchParams = useSearchParams();
  const query = searchParams.get('q') || '';
  
  const { data: results, isLoading, error } = useSearch({ q: query }, query.length >= 2);
  
  if (!query || query.length < 2) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center py-12">
          <Search className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">Enter at least 2 characters to search</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Search Results</h1>
        <p className="text-gray-600">
          Showing results for <span className="font-medium">&quot;{query}&quot;</span>
        </p>
      </div>
      
      {/* Loading */}
      {isLoading && (
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      )}
      
      {/* Error */}
      {error && (
        <div className="text-center py-12">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600">Error loading search results</p>
        </div>
      )}
      
      {/* Results */}
      {!isLoading && results && (
        <>
          <div className="mb-6 text-sm text-gray-600">
            Found {results.length} results
          </div>
          
          {results.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <Search className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">No results found for &quot;{query}&quot;</p>
              <p className="text-sm text-gray-500 mt-2">
                Try different keywords or browse topics
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {results.map((result) => (
                <Link
                  key={`${result.type}-${result.id}`}
                  href={
                    result.type === 'article'
                      ? `/articles/${result.id}`
                      : `/topics/${result.id}/articles`
                  }
                >
                  <Card className="hover:shadow-lg transition-shadow">
                    <CardHeader>
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            {result.type === 'article' ? (
                              <FileText className="h-4 w-4 text-blue-500" />
                            ) : (
                              <Folder className="h-4 w-4 text-green-500" />
                            )}
                            <Badge variant="secondary">
                              {result.type}
                            </Badge>
                          </div>
                          
                          <CardTitle className="text-xl hover:text-blue-600 transition-colors">
                            {result.title}
                          </CardTitle>
                        </div>
                      </div>
                    </CardHeader>
                    
                    <CardContent>
                      <p className="text-sm text-gray-600 line-clamp-2">
                        {result.snippet}
                      </p>
                      
                      {/* Metadata */}
                      {result.metadata && (
                        <div className="mt-3 flex flex-wrap gap-2 text-xs text-gray-500">
                          {result.metadata.topic && (
                            <span>Topic: {result.metadata.topic}</span>
                          )}
                          {result.metadata.subject && (
                            <span>Subject: {result.metadata.subject}</span>
                          )}
                          {result.metadata.word_count && (
                            <span>{result.metadata.word_count} words</span>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
