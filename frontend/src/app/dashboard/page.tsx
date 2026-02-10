/**
 * User dashboard page
 */

'use client';

import { useArticles } from '@/lib/hooks/use-articles';
import { useTopics } from '@/lib/hooks/use-topics';
import StatsCards from '@/components/dashboard/stats-cards';
import ArticleCard from '@/components/articles/article-card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Sparkles, ArrowRight, BookOpen, FileText } from 'lucide-react';
import Link from 'next/link';

export default function DashboardPage() {
    const { data: articlesData, isLoading: articlesLoading } = useArticles({ ordering: '-created_at' });
    const { data: topicsData, isLoading: topicsLoading } = useTopics();

    const articles = articlesData?.results || [];
    const topics = topicsData?.results || [];
    const recentArticles = articles.slice(0, 3);

    return (
        <div className="container mx-auto px-4 py-8">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-4xl font-bold mb-2">Dashboard</h1>
                <p className="text-gray-600">
                    Welcome back! Here's your learning overview.
                </p>
            </div>

            {/* Stats */}
            <div className="mb-12">
                <StatsCards
                    articlesRead={0}
                    totalArticles={articles.length}
                    hoursSpent={0}
                    topicsCompleted={0}
                />
            </div>

            {/* Recent Articles */}
            <div className="mb-12">
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-2xl font-bold">Recent Articles</h2>
                    <Link href="/articles">
                        <Button variant="outline" className="gap-2">
                            View All
                            <ArrowRight className="h-4 w-4" />
                        </Button>
                    </Link>
                </div>

                {articlesLoading ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {[...Array(3)].map((_, i) => (
                            <Skeleton key={i} className="h-64" />
                        ))}
                    </div>
                ) : recentArticles.length === 0 ? (
                    <div className="text-center py-12 bg-gray-50 rounded-lg">
                        <p className="text-gray-600 mb-4">No articles yet</p>
                        <Link href="/generate">
                            <Button className="gap-2">
                                <Sparkles className="h-4 w-4" />
                                Generate Your First Article
                            </Button>
                        </Link>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {recentArticles.map((article) => (
                            <ArticleCard key={article.id} article={article} />
                        ))}
                    </div>
                )}
            </div>

            {/* Quick Actions */}
            <div>
                <h2 className="text-2xl font-bold mb-6">Quick Actions</h2>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <Link href="/generate">
                        <Button variant="outline" className="w-full h-32 flex-col gap-2" size="lg">
                            <Sparkles className="h-8 w-8" />
                            <span>Generate Article</span>
                        </Button>
                    </Link>

                    <Link href="/topics">
                        <Button variant="outline" className="w-full h-32 flex-col gap-2" size="lg">
                            <BookOpen className="h-8 w-8" />
                            <span>Browse Topics</span>
                        </Button>
                    </Link>

                    <Link href="/articles">
                        <Button variant="outline" className="w-full h-32 flex-col gap-2" size="lg">
                            <FileText className="h-8 w-8" />
                            <span>Read Articles</span>
                        </Button>
                    </Link>
                </div>
            </div>
        </div>
    );
}
