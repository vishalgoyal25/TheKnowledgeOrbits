"use client";

import { toast } from "@/hooks/use-toast";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { articlesAPI } from "../api/articles";
import { getErrorMessage } from "../api/client";
import { ArticleGenerationRequest } from "../types";

export function useGenerateArticle() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: async (data: ArticleGenerationRequest) => {
      const response = await articlesAPI.generate(data);
      const jobId = response.job_id;

      // Poll every 3 seconds
      // eslint-disable-next-line no-constant-condition
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const statusResponse = await articlesAPI.getJobStatus(jobId);

        if (statusResponse.status === "completed") {
          return statusResponse;
        } else if (statusResponse.status === "failed") {
          throw new Error("Article generation failed during processing.");
        }
        // If pending or processing, loop continues
      }
    },
    onSuccess: (statusResponse) => {
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      toast({
        title: "Article generated!",
        description: "Your article is ready to read.",
      });
      if (statusResponse.article_id) {
        router.push(`/articles/${statusResponse.article_id}`);
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
