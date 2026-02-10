/**
 * Source attribution viewer
 */

'use client';

import { ArticleSourceMap } from '@/lib/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { FileText, Star } from 'lucide-react';

interface SourceViewerProps {
    sources: ArticleSourceMap[];
}

export default function SourceViewer({ sources }: SourceViewerProps) {
    return (
        <div className="space-y-4">
            {sources.map((source, index) => (
                <Card key={source.id}>
                    <CardHeader>
                        <div className="flex items-start justify-between">
                            <CardTitle className="text-lg">
                                Source {index + 1}
                            </CardTitle>

                            <div className="flex items-center gap-2">
                                <Badge variant="secondary">
                                    {source.chunk.source_type === 'static' ? 'Textbook' : 'Current Affairs'}
                                </Badge>

                                <div className="flex items-center gap-1 text-sm text-gray-600">
                                    <Star className="h-4 w-4" />
                                    <span>{(source.relevance_weight * 100).toFixed(0)}%</span>
                                </div>
                            </div>
                        </div>

                        {/* Document info */}
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                            <FileText className="h-4 w-4" />
                            <span>{source.chunk.document_title}</span>
                            {source.chunk.chapter_name && (
                                <>
                                    <span>•</span>
                                    <span>{source.chunk.chapter_name}</span>
                                </>
                            )}
                            {source.chunk.page_number && (
                                <>
                                    <span>•</span>
                                    <span>Page {source.chunk.page_number}</span>
                                </>
                            )}
                        </div>
                    </CardHeader>

                    <CardContent>
                        {/* Chunk text */}
                        <div className="prose prose-sm max-w-none">
                            <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">
                                {source.chunk.chunk_text}
                            </p>
                        </div>

                        {/* Metadata */}
                        <div className="mt-4 pt-4 border-t flex items-center justify-between text-xs text-gray-500">
                            <span>Chunk {source.chunk.chunk_index}</span>
                            <Badge variant="outline" className="text-xs">
                                {source.chunk.quality_flag}
                            </Badge>
                        </div>
                    </CardContent>
                </Card>
            ))}
        </div>
    );
}
