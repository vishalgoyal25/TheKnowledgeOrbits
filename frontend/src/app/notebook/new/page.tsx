/**
 * New article generation page
 * TODO: Implement full generation form in upcoming phase
 */

"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

export default function NewArticlePage() {
  const router = useRouter();

  return (
    <div className="max-w-2xl mx-auto p-6">
      <Button
        variant="ghost"
        onClick={() => router.back()}
        className="mb-6 flex items-center gap-2"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Notebook
      </Button>

      <h1 className="text-3xl font-bold text-gray-900 mb-4">
        Generate New Article
      </h1>
      <p className="text-gray-600">
        Article generation form will be implemented in the upcoming phase.
      </p>
    </div>
  );
}
