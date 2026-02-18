/**
 * Article list — renders a list of article cards
 * TODO: Enhance with sorting/filtering in upcoming phase
 */

'use client';

import { Article } from '@/types/notebook';
import ArticleCard from './ArticleCard';

interface Props {
    articles: Article[];
    onDelete: () => void;
}

export default function ArticleList({ articles, onDelete }: Props) {
    return (
        <div className="space-y-4">
            {articles.map(article => (
                <ArticleCard key={article.id} article={article} onDelete={onDelete} />
            ))}
        </div>
    );
}
