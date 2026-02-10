/**
 * Article listing page
 */

'use client';

import { useState } from 'react';
import { useArticles } from '@/lib/hooks/use-articles';
import ArticleCard from '@/components/articles/article-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Search, Filter } from 'lucide-react';

export default function ArticlesPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  
  const { data, isLoading, error } = useArticles({
    review_status: filterStatus || undefined,
    ordering: '-created_at',
  });
  
  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center text-red-600">
          Error loading articles. Please try again.
        </div>
      </div>
    );
  }
  
  const articles = data?.results || [];
  
  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Articles</h1>
        <p className="text-gray-600">
          Browse AI-generated articles on UPSC topics
        </p>
      </div>
      
      {/* Filters */}
      <div className="mb-8 flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search articles..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        
        <Button variant="outline" className="gap-2">
          <Filter className="h-4 w-4" />
          Filters
        </Button>
      </div>
      
      {/* Stats */}
      <div className="mb-6 text-sm text-gray-600">
        Showing {articles.length} of {data?.count || 0} articles
      </div>
      
      {/* Article Grid */}
      {articles.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-600">No articles found.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {articles.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      )}
    </div>
  );
}
