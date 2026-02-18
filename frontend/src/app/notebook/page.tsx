'use client';

import { useState } from 'react';
import { useNotebook } from '@/lib/hooks/use-notebook';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import ArticleCard from '@/components/notebook/ArticleCard';
import EmptyState from '@/components/notebook/EmptyState';
import { PlusCircle, Search, Loader2 } from 'lucide-react';

export default function NotebookPage() {
  const router = useRouter();
  const { data: articles, isLoading, refetch } = useNotebook();
  const [searchQuery, setSearchQuery] = useState('');

  // Filter articles by search
  const filteredArticles = articles?.filter(article =>
    article.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    article.topic.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">My Notebook</h1>
            <p className="text-gray-600 mt-1">Your private AI-generated articles</p>
          </div>
          <Button onClick={() => router.push('/articles/generate')} className="flex items-center gap-2">
            <PlusCircle className="h-5 w-5" />
            New Article
          </Button>
        </div>

        {/* Search Bar */}
        <Card className="p-4 mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <Input
              type="text"
              placeholder="Search articles by title or topic..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
        </Card>

        {/* Articles List */}
        {filteredArticles && filteredArticles.length > 0 ? (
          <div className="space-y-4">
            {filteredArticles.map(article => (
              <ArticleCard
                key={article.id}
                article={article}
                onDelete={() => refetch()}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            title={searchQuery ? 'No articles found' : 'No articles yet'}
            description={
              searchQuery
                ? 'Try a different search term'
                : 'Generate your first article to get started'
            }
            actionLabel="Generate Article"
            onAction={() => router.push('/articles/generate')}
          />
        )}
      </div>
    </div>
  );
}

