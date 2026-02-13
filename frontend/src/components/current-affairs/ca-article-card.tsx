/**
 * CA Article Card Component
 */

'use client';

import Link from 'next/link';
import { CAArticle } from '@/lib/types';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ExternalLink, Calendar, FileText, Sparkles } from 'lucide-react';
import { formatRelativeTime } from '@/lib/utils';

interface CAArticleCardProps {
  article: CAArticle;
}

export default function CAArticleCard({ article }: CAArticleCardProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'processing':
        return 'bg-blue-100 text-blue-800';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };
  
  return (
    <Card className="h-full transition-all hover:shadow-lg">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-lg line-clamp-2 flex-1">
            {article.title}
          </CardTitle>
          
          <Badge variant="secondary" className={getStatusColor(article.processing_status)}>
            {article.processing_status}
          </Badge>
        </div>
        
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <Sparkles className="h-4 w-4 text-blue-500" />
          <span>{article.source_name}</span>
        </div>
      </CardHeader>
      
      <CardContent>
        <p className="text-sm text-gray-600 line-clamp-3">
          {article.summary || article.content.substring(0, 150) + '...'}
        </p>
        
        {/* Categories */}
        {article.categories && article.categories.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {article.categories.slice(0, 3).map((category, idx) => (
              <Badge key={idx} variant="outline" className="text-xs">
                {category}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
      
      <CardFooter className="flex items-center justify-between text-sm text-gray-500">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1">
            <Calendar className="h-4 w-4" />
            <span>{formatRelativeTime(article.published_at)}</span>
          </div>
          
          {article.processing_status === 'completed' && (
            <div className="flex items-center gap-1">
              <FileText className="h-4 w-4" />
              <span>{article.chunk_count} chunks</span>
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          <Link href={`/current-affairs/${article.id}`}>
            <Badge variant="outline" className="cursor-pointer hover:bg-gray-100">
              View
            </Badge>
          </Link>
          
          <a href={article.url} target="_blank" rel="noopener noreferrer">
            <Badge variant="outline" className="cursor-pointer hover:bg-gray-100 gap-1">
              Source <ExternalLink className="h-3 w-3" />
            </Badge>
          </a>
        </div>
      </CardFooter>
    </Card>
  );
}
