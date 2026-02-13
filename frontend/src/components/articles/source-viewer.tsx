'use client';

import { ArticleSourceMap } from '@/lib/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { FileText, Star, Book, Newspaper } from 'lucide-react';

interface SourceViewerProps {
    sources: ArticleSourceMap[];
}

export default function SourceViewer({ sources }: SourceViewerProps) {
    // 🆕 Separate static and CA sources
    // Check both flattened source_type (if available) and nested chunk.source_type
    const staticSources = sources.filter(s => (s.source_type === 'static' || s.chunk.source_type === 'static'));
    const caSources = sources.filter(s => (s.source_type === 'dynamic' || s.chunk.source_type === 'dynamic'));

    return (
        <div className="space-y-4">
            {/* 🆕 Static Sources Section */}
            {staticSources.length > 0 && (
                <div>
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                        <Book className="h-5 w-5 text-green-600" />
                        Textbook Sources ({staticSources.length})
                    </h3>
                    <div className="space-y-3">
                        {staticSources.map((source, idx) => (
                            <Card key={source.id || idx}>
                                <CardHeader className="pb-2">
                                    <div className="flex justify-between">
                                        <span className="font-medium text-sm">Source {idx + 1}</span>
                                        <Badge variant="secondary" className="text-xs">
                                            Relevance: {(source.relevance_weight * 100).toFixed(0)}%
                                        </Badge>
                                    </div>
                                </CardHeader>
                                <CardContent className="pt-0">
                                    <div className="flex items-start justify-between gap-2 mb-2">
                                        <p className="text-sm text-gray-700 flex-1 leading-relaxed whitespace-pre-wrap">
                                            {source.chunk_text || source.chunk.chunk_text}
                                        </p>
                                    </div>

                                    <div className="flex items-center gap-2 mt-2">
                                        {source.chunk.page_number && (
                                            <Badge variant="outline" className="flex-shrink-0 text-xs">
                                                Page {source.chunk.page_number}
                                            </Badge>
                                        )}
                                        {(source.chapter_name || source.chunk.chapter_name) && (
                                            <span className="text-xs text-gray-500">
                                                • {source.chapter_name || source.chunk.chapter_name}
                                            </span>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </div>
            )}

            {/* 🆕 CA Sources Section */}
            {caSources.length > 0 && (
                <div>
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                        <Newspaper className="h-5 w-5 text-blue-600" />
                        Current Affairs Sources ({caSources.length})
                    </h3>
                    <div className="space-y-3">
                        {caSources.map((source, idx) => (
                            <Card key={source.id || idx} className="bg-blue-50">
                                <CardContent className="pt-4">
                                    <div className="flex items-start justify-between gap-2 mb-2">
                                        <p className="text-sm text-gray-700 flex-1">
                                            {source.chunk_text || source.chunk.chunk_text}
                                        </p>
                                        <Badge className="bg-blue-100 text-blue-800 flex-shrink-0">
                                            Recent
                                        </Badge>
                                    </div>
                                    {(source.article_title || source.chunk.document_title) && (
                                        <p className="text-xs text-gray-600">
                                            From: {source.article_title || source.chunk.document_title}
                                        </p>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
