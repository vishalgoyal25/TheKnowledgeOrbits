/**
 * CA Source Status Component - Shows scraping status
 */

'use client';

import { CASource } from '@/lib/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { formatRelativeTime } from '@/lib/utils';

interface CASourceStatusProps {
  sources: CASource[];
}

export default function CASourceStatus({ sources }: CASourceStatusProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {sources.map((source) => (
        <Card key={source.id}>
          <CardHeader>
            <div className="flex items-start justify-between">
              <CardTitle className="text-lg">{source.name}</CardTitle>
              
              {source.is_active ? (
                <Badge className="bg-green-100 text-green-800 gap-1">
                  <CheckCircle className="h-3 w-3" />
                  Active
                </Badge>
              ) : (
                <Badge variant="secondary" className="gap-1">
                  <AlertCircle className="h-3 w-3" />
                  Inactive
                </Badge>
              )}
            </div>
          </CardHeader>
          
          <CardContent className="space-y-3">
            {/* Statistics */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-gray-600">Articles Scraped</div>
                <div className="text-2xl font-bold">{source.article_count}</div>
              </div>
              
              <div>
                <div className="text-gray-600">Frequency</div>
                <div className="text-lg font-semibold capitalize">{source.scrape_frequency}</div>
              </div>
            </div>
            
            {/* Last scraped */}
            {source.last_scraped_at && (
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Clock className="h-4 w-4" />
                <span>Last scraped {formatRelativeTime(source.last_scraped_at)}</span>
              </div>
            )}
            
            {/* URL */}
            <div className="pt-2 border-t">
              <a 
                href={source.url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-xs text-blue-600 hover:underline truncate block"
              >
                {source.url}
              </a>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
