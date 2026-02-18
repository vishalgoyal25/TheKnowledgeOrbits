'use client';

import { ExternalLink, BookOpen } from 'lucide-react';

interface Source {
    title: string;
    document_title?: string;
    chunk_index?: number;
    relevance_score?: number;
}

interface SourceAttributionProps {
    sources: Source[];
}

export default function SourceAttribution({ sources }: SourceAttributionProps) {
    if (!sources || sources.length === 0) return null;

    return (
        <div className="mt-6 pt-6 border-t border-gray-100">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide flex items-center gap-2 mb-3">
                <BookOpen className="h-4 w-4" />
                Sources
            </h3>
            <div className="space-y-2">
                {sources.map((source, idx) => (
                    <div
                        key={idx}
                        className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg text-sm hover:bg-gray-100 transition-colors"
                    >
                        <span className="flex-shrink-0 w-5 h-5 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-bold">
                            {idx + 1}
                        </span>
                        <div className="flex-1 min-w-0">
                            <p className="font-medium text-gray-800 truncate">
                                {source.document_title || source.title}
                            </p>
                            {source.chunk_index !== undefined && (
                                <p className="text-xs text-gray-400 mt-0.5">
                                    Section {source.chunk_index + 1}
                                    {source.relevance_score !== undefined && (
                                        <span className="ml-2 text-blue-500">
                                            {Math.round(source.relevance_score * 100)}% relevant
                                        </span>
                                    )}
                                </p>
                            )}
                        </div>
                        <ExternalLink className="h-3.5 w-3.5 text-gray-300 flex-shrink-0 mt-0.5" />
                    </div>
                ))}
            </div>
        </div>
    );
}
