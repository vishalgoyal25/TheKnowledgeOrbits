'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { articlesAPI } from '../api/articles';
import { ArticleGenerationRequest, ArticleGenerationResponse } from '../types'; // Correct import path might be ../types

export function useGenerateArticle() {
    const queryClient = useQueryClient();
    const router = useRouter();

    return useMutation({
        mutationFn: (data: ArticleGenerationRequest) => articlesAPI.generate(data),
        onSuccess: (data: ArticleGenerationResponse) => {
            // Invalidate relevant queries
            queryClient.invalidateQueries({ queryKey: ['articles'] });
            // Redirect to the new article
            if (data.article?.id) {
                router.push(`/articles/${data.article.id}`);
            }
        },
    });
}
