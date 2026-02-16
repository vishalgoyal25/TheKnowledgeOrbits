/**
 * Article Metadata Component - Displays article info, status, and learning stats
 */

import React from 'react';
import { Article } from '@/lib/types';
import {
    Clock,
    Calendar,
    Tag,
    CheckCircle2,
    FileText,
    Sparkles,
    Award
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { formatDate } from '@/lib/utils';

interface Props {
    article: Article;
    className?: string;
}

export default function ArticleMetadata({ article, className }: Props) {
    const isAI = article.generation_type.includes('ai');

    return (
        <div className={`flex flex-wrap items-center gap-y-3 gap-x-6 text-sm text-gray-500 ${className}`}>
            {/* Generation Source */}
            <div className="flex items-center gap-2">
                {isAI ? (
                    <Badge variant="secondary" className="bg-blue-50 text-blue-700 hover:bg-blue-100 border-blue-100 px-2 flex items-center gap-1">
                        <Sparkles className="h-3 w-3" />
                        AI Generated
                    </Badge>
                ) : (
                    <Badge variant="secondary" className="bg-green-50 text-green-700 hover:bg-green-100 border-green-100 px-2 flex items-center gap-1">
                        <CheckCircle2 className="h-3 w-3" />
                        Verified Source
                    </Badge>
                )}
            </div>

            {/* Read Time */}
            <div className="flex items-center gap-1.5">
                <Clock className="h-4 w-4 text-gray-400" />
                <span>{article.read_time || 5} min read</span>
            </div>

            {/* Date */}
            <div className="flex items-center gap-1.5">
                <Calendar className="h-4 w-4 text-gray-400" />
                <span>{formatDate(article.created_at)}</span>
            </div>

            {/* Topic Tag */}
            <div className="flex items-center gap-1.5">
                <Tag className="h-4 w-4 text-gray-400" />
                <span className="font-medium text-gray-700">{article.topic.name}</span>
            </div>

            {/* Word Count */}
            <div className="flex items-center gap-1.5 border-l pl-6 ml-auto">
                <FileText className="h-4 w-4 text-gray-400" />
                <span>{article.word_count} words</span>
            </div>

            {/* Quality Score */}
            {article.quality_score && (
                <div className="flex items-center gap-1.5">
                    <Award className="h-4 w-4 text-orange-400" />
                    <span className="font-bold text-orange-700">{article.quality_score}% Match</span>
                </div>
            )}
        </div>
    );
}
