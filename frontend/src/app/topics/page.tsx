/**
 * Topics listing page
 */

'use client';

import { useState } from 'react';
import { useTopics } from '@/lib/hooks/use-topics';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Search, Filter, BookOpen, Layers, Hash } from 'lucide-react';
import Link from 'next/link';

export default function TopicsPage() {
    const [searchTerm, setSearchTerm] = useState('');
    const { data, isLoading, error } = useTopics({
        page_size: 50,
    });

    if (isLoading) {
        return (
            <div className="container mx-auto px-4 py-8">
                <div className="mb-8">
                    <Skeleton className="h-10 w-48 mb-2" />
                    <Skeleton className="h-5 w-96" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {[...Array(6)].map((_, i) => (
                        <Skeleton key={i} className="h-48" />
                    ))}
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="container mx-auto px-4 py-8">
                <div className="text-center text-red-600 bg-red-50 p-8 rounded-lg border border-red-100">
                    <h3 className="text-lg font-semibold mb-2">Error Loading Topics</h3>
                    <p>Please try again later.</p>
                </div>
            </div>
        );
    }

    const topics = data?.results || [];

    // Client-side filter for now since API search might need specific param
    const filteredTopics = topics.filter(topic =>
        topic.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        topic.description?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="container mx-auto px-4 py-8">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-4xl font-bold mb-2">Topics</h1>
                <p className="text-gray-600">
                    Explore the knowledge graph and syllabus topics
                </p>
            </div>

            {/* Filters */}
            <div className="mb-8 flex gap-4">
                <div className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <Input
                        placeholder="Search topics..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="pl-10"
                    />
                </div>

                <Button variant="outline" className="gap-2">
                    <Filter className="h-4 w-4" />
                    Filter
                </Button>
            </div>

            {/* Topics Grid */}
            {filteredTopics.length === 0 ? (
                <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed">
                    <p className="text-gray-600">No topics found matching your search.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredTopics.map((topic) => (
                        <Link key={topic.id} href={`/topics/${topic.id}`}>
                            <Card className="h-full hover:shadow-lg transition-all hover:scale-[1.02] cursor-pointer">
                                <CardHeader>
                                    <div className="flex justify-between items-start gap-2">
                                        <CardTitle className="text-lg line-clamp-2">{topic.name}</CardTitle>
                                        <Badge variant={topic.topic_type === 'syllabus' ? 'default' : 'secondary'}>
                                            {topic.topic_type}
                                        </Badge>
                                    </div>
                                    <CardDescription className="line-clamp-2">
                                        {topic.description || 'No description available'}
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="flex flex-col gap-3 text-sm text-gray-500">
                                        <div className="flex items-center gap-2">
                                            <BookOpen className="h-4 w-4" />
                                            <span className="truncate">{topic.subject_name}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Layers className="h-4 w-4" />
                                            <span className="truncate">{topic.module_name}</span>
                                        </div>
                                        {topic.keywords && topic.keywords.length > 0 && (
                                            <div className="flex items-center gap-2 mt-2">
                                                <Hash className="h-4 w-4" />
                                                <div className="flex gap-1 flex-wrap">
                                                    {topic.keywords.slice(0, 3).map((kw, i) => (
                                                        <span key={i} className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">
                                                            {kw}
                                                        </span>
                                                    ))}
                                                    {topic.keywords.length > 3 && (
                                                        <span className="text-xs">+{topic.keywords.length - 3}</span>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    );
}
