/**
 * Articles by topic page
 */

'use client';

import { useParams } from 'next/navigation';
import { useTopic } from '@/lib/hooks/use-topics';
import { useArticlesByTopic } from '@/lib/hooks/use-articles';
import ArticleCard from '@/components/articles/article-card';
import BreadcrumbNav from '@/components/topics/breadcrumb-nav';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Sparkles, FileText, Newspaper } from 'lucide-react';
import Link from 'next/link';
import { getDifficultyColor } from '@/lib/utils'; // Keep this import

import { useCAChunksForTopic } from '@/lib/hooks/use-current-affairs';
import CATopicBadge from '@/components/current-affairs/ca-topic-badge';

export default function TopicArticlesPage() {
  const params = useParams();
  const topicId = params.id as string;

  const { data: topic, isLoading: topicLoading } = useTopic(topicId);
  const { data: articlesData, isLoading: articlesLoading } = useArticlesByTopic(topicId);
  const { data: caChunks, isLoading: caChunksLoading } = useCAChunksForTopic(topicId, 30);

  if (topicLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="h-8 w-full max-w-2xl mb-8" />
        <Skeleton className="h-32 w-full mb-8" />
      </div>
    );
  }

  if (!topic) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center text-red-600">Topic not found</div>
      </div>
    );
  }

  const articles = articlesData?.results || [];

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <div className="mb-6">
        <BreadcrumbNav topic={topic} currentPage="Articles" />
      </div>

      {/* Topic Header */}
      <div className="mb-8 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex-1">
            <h1 className="text-3xl font-bold mb-2">{topic.name}</h1>
            <p className="text-gray-700">{topic.description}</p>
          </div>

          <div className="flex flex-col gap-2">
            {topic.difficulty_level && (
              <Badge className={getDifficultyColor(topic.difficulty_level)}>
                {topic.difficulty_level}
              </Badge>
            )}

            <Link href={`/generate?topic_id=${topic.id}`}>
              <Button className="gap-2">
                <Sparkles className="h-4 w-4" />
                Generate Article
              </Button>
            </Link>
          </div>
        </div>

        {/* 🆕 CA Badge */}
        <div className="flex items-center gap-2">
          <p className="text-gray-600">
            {articles?.length || 0} articles available
          </p>
          {caChunks && caChunks.length > 0 && (
            <CATopicBadge count={caChunks.length} />
          )}
        </div>
      </div>

      {/* 🆕 CA Preview Section */}
      {caChunks && caChunks.length > 0 && (
        <div className="mb-8 p-4 bg-blue-50 rounded-lg">
          <h3 className="font-semibold mb-2 flex items-center gap-2">
            <Newspaper className="h-5 w-5 text-blue-600" />
            Recent Current Affairs ({caChunks.length})
          </h3>
          <p className="text-sm text-gray-700">
            Latest news and updates related to this topic from the past 30 days.
            Generate an article with CA enabled to see integrated content.
          </p>
        </div>
      )}

      {/* Keywords */}
      {topic.keywords && topic.keywords.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-8">
          {topic.keywords.map((keyword, idx) => (
            <Badge key={idx} variant="secondary">
              {keyword}
            </Badge>
          ))}
        </div>
      )}

      {/* Articles */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold">Articles</h2>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <FileText className="h-4 w-4" />
            <span>{articles.length} articles</span>
          </div>
        </div>
      </div>

      {articlesLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      ) : articles.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-600 mb-4">No articles yet for this topic</p>
          <Link href={`/generate?topic_id=${topic.id}`}>
            <Button className="gap-2">
              <Sparkles className="h-4 w-4" />
              Generate First Article
            </Button>
          </Link>
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
