/**
 * Topic articles listing page (redirects or displays filtered view)
 * 
 * Note: Since the detail page already lists articles, this page acts as a 
 * dedicated view for just the articles, useful for deeper linking or specific layouts.
 */

'use client';

import { useParams } from 'next/navigation';
import { useTopic } from '@/lib/hooks/use-topics';
import { useArticlesByTopic } from '@/lib/hooks/use-articles';
import ArticleCard from '@/components/articles/article-card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { Article } from '@/lib/types';

export default function TopicArticlesPage() {
    const params = useParams();
    const topicId = params.id as string;

    const { data: topic } = useTopic(topicId);
    const { data: articlesData, isLoading, error } = useArticlesByTopic(topicId);

    if (isLoading) {
        return (
            <div className="container mx-auto px-4 py-8">
                <Skeleton className="h-8 w-32 mb-8" />
                <Skeleton className="h-10 w-64 mb-6" />
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
                    Error loading articles.
                </div>
            </div>
        );
    }

    const articles = articlesData?.results || [];

    return (
        <div className="container mx-auto px-4 py-8">
            {/* Back button */}
            <div className="mb-8">
                <Link href={`/topics/${topicId}`}>
                    <Button variant="ghost" className="gap-2">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Topic Details
                    </Button>
                </Link>
            </div>

            <div className="mb-8">
                <h1 className="text-3xl font-bold mb-2">
                    Articles: {topic?.name || 'Loading...'}
                </h1>
                <p className="text-gray-600">
                    All study materials and generated content for this topic.
                </p>
            </div>

            {articles.length === 0 ? (
                <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed">
                    <p className="text-gray-600">No articles found for this topic.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {articles.map((article: Article) => (
                        <ArticleCard key={article.id} article={article} />
                    ))}
                </div>
            )}
        </div>
    );
}
