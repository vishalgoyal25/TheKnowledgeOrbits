"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { articlesAPI } from "../api/articles";
import { ArticleGenerationRequest, ArticleGenerationResponse } from "../types";
import { toast } from "@/hooks/use-toast";
import { getErrorMessage } from "../api/client";

export function useGenerateArticle() {
    const queryClient = useQueryClient();
    const router = useRouter();

    return useMutation({
        mutationFn: (data: ArticleGenerationRequest) => articlesAPI.generate(data),
        onSuccess: (data: ArticleGenerationResponse) => {
            queryClient.invalidateQueries({ queryKey: ["articles"] });
            toast({
                title: "Article generated!",
                description: "Your article is ready to read.",
            });
            if (data.article?.id) {
                router.push(`/articles/${data.article.id}`);
            }
        },
        onError: (error: unknown) => {
            const message = getErrorMessage(error);
            toast({
                title: "Generation failed",
                description: message,
                variant: "destructive",
            });
        },
    });
}
