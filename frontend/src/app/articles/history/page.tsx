'use client';

import { useReadingHistory } from '@/lib/hooks/use-reading-progress';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { History, BookOpen, Clock, CheckCircle } from 'lucide-react';
import Link from 'next/link';
import { formatDistanceToNow } from 'date-fns';

export default function ReadingHistoryPage() {
    const { data: history, isLoading } = useReadingHistory();

    if (isLoading) {
        return (
            <div className="container mx-auto p-6 max-w-4xl space-y-4">
                <Skeleton className="h-12 w-64 mb-6" />
                {[1, 2, 3].map(i => (
                    <Skeleton key={i} className="h-32 w-full rounded-xl" />
                ))}
            </div>
        );
    }

    return (
        <div className="container mx-auto p-6 max-w-4xl">
            <div className="mb-8 flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold flex items-center gap-3 text-gray-900">
                        <History className="h-8 w-8 text-blue-600" />
                        Reading History
                    </h1>
                    <p className="text-gray-600 mt-2 text-lg">Track your progress across the knowledge universe.</p>
                </div>
                <Link href="/articles">
                    <Button className="gap-2">
                        <BookOpen className="h-5 w-5" />
                        Browse More
                    </Button>
                </Link>
            </div>

            {!history || history.length === 0 ? (
                <div className="text-center py-16 bg-gray-50 rounded-xl border border-dashed border-gray-200">
                    <BookOpen className="h-16 w-16 text-gray-300 mx-auto mb-4" />
                    <h3 className="text-xl font-medium text-gray-900 mb-2">No reading history yet</h3>
                    <p className="text-gray-500 mb-6">Start reading articles to see your progress here.</p>
                    <Link href="/articles">
                        <Button size="lg">Browse Articles</Button>
                    </Link>
                </div>
            ) : (
                <div className="space-y-4">
                    {history.map((item: any) => {
                        const isCompleted = item.percent_read >= 75;
                        return (
                            <Card key={item.id} className="hover:shadow-md transition-all duration-200 border-gray-100">
                                <CardContent className="p-6">
                                    <div className="flex flex-col md:flex-row justify-between gap-4 mb-4">
                                        <div className="space-y-1">
                                            <h3 className="font-bold text-lg text-gray-900">{item.article_title || 'Untitled Article'}</h3>
                                            <div className="flex items-center gap-2">
                                                <span className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs font-medium rounded-full">
                                                    {item.topic_name || 'General'}
                                                </span>
                                            </div>
                                        </div>
                                        <Link href={`/articles/${item.article_id}`}>
                                            <Button variant={isCompleted ? "outline" : "default"} size="sm">
                                                {isCompleted ? 'Read Again' : 'Continue'}
                                            </Button>
                                        </Link>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex justify-between text-sm items-center">
                                            <span className={`flex items-center gap-1.5 font-medium ${isCompleted ? "text-green-600" : "text-blue-600"}`}>
                                                {isCompleted ? (
                                                    <>
                                                        <CheckCircle className="h-4 w-4" />
                                                        Completed
                                                    </>
                                                ) : (
                                                    "In Progress"
                                                )}
                                            </span>
                                            <span className="text-gray-500 font-medium">{Math.round(item.percent_read)}%</span>
                                        </div>
                                        <Progress value={item.percent_read} className={`h-2 ${isCompleted ? "bg-green-100" : "bg-blue-100"}`} />
                                    </div>

                                    <div className="mt-4 flex items-center gap-2 text-xs text-gray-400">
                                        <Clock className="h-3 w-3" />
                                        <span>Last read {item.updated_at ? formatDistanceToNow(new Date(item.updated_at), { addSuffix: true }) : 'recently'}</span>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
