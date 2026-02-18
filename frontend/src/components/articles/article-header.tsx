'use client';

import { Article } from '@/lib/types';
import { Article as NotebookArticle } from '@/types/notebook';
import BookmarkButton from './bookmark-button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Calendar, Clock, FileText, Star, Tag } from 'lucide-react';
import { formatDate, getQualityColor } from '@/lib/utils';

interface Props {
    article: Article;
}

export default function ArticleHeader({ article }: Props) {
    return (
        <header className="mb-8">
            {/* Title */}
            <h1 className="text-4xl font-bold text-gray-900 mb-4 leading-tight">
                {article.title}
            </h1>

            {/* Metadata */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4 text-sm text-gray-600">
                    <span className="flex items-center gap-1">
                        <Clock className="h-4 w-4" />
                        {article.read_time} min read
                    </span>
                    <span className="flex items-center gap-1">
                        <Tag className="h-4 w-4" />
                        {article.topic.name}
                    </span>
                    <span>{article.word_count.toLocaleString()} words</span>
                    <span className="flex items-center gap-1">
                        <Calendar className="h-4 w-4" />
                        {formatDate(article.created_at)}
                    </span>
                    <div className="flex items-center gap-1">
                        <Star className={`h-4 w-4 ${getQualityColor(article.quality_score)}`} />
                        <span className={getQualityColor(article.quality_score)}>
                            Quality: {article.quality_score.toFixed(0)}%
                        </span>
                    </div>
                </div>

                <BookmarkButton
                    contentType="article"
                    contentId={article.id}
                    title={article.title}
                />
            </div>

            {/* Summary */}
            {article.summary && (
                <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6">
                    <p className="text-blue-900 font-medium text-sm">Summary</p>
                    <p className="text-blue-800 mt-1">{article.summary}</p>
                </div>
            )}

            <Separator />
        </header>
    );
}
