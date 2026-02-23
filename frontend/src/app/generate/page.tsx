"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useTopic } from "@/lib/hooks/use-topics";
import { Topic } from "@/lib/types";
import TopicSelector from "@/components/generate/topic-selector";
import GenerationProgress from "@/components/generate/generation-progress";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useGenerateArticle } from "@/lib/hooks/use-article-generation";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Sparkles, Newspaper, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AxiosError } from "axios";
import { ApiError } from "@/lib/types";

import { Suspense } from "react";

/**
 * GeneratePageContent - Handles the interactive state for RAG-based article generation.
 * Manages topic selection, Current Affairs (CA) toggles, and artificial progress simulation
 * during the asynchronous generation process.
 */
function GeneratePageContent() {
  const [includeCA, setIncludeCA] = useState(true);
  const searchParams = useSearchParams();
  const topicIdFromUrl = searchParams.get("topic_id");

  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null);
  const [progress, setProgress] = useState(0);

  const { data: topicFromUrl } = useTopic(topicIdFromUrl);
  const generateMutation = useGenerateArticle();
  const selectedTopicId = selectedTopic?.id;

  // Simulate progress while generating to manage user expectations during long RAG cycles
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (generateMutation.isPending) {
      setProgress(5);
      interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) return prev; // Hold at 90% until backend confirms completion
          return prev + Math.random() * 12;
        });
      }, 1200);
    } else if (generateMutation.isSuccess) {
      setProgress(100);
      setTimeout(() => setProgress(0), 1500);
    } else {
      setProgress(0);
    }
    return () => clearInterval(interval);
  }, [generateMutation.isPending, generateMutation.isSuccess]);

  /**
   * Initiates the AI article generation request.
   */
  const handleGenerate = () => {
    if (!selectedTopicId) return;
    generateMutation.mutate({
      topic_id: selectedTopicId,
      include_ca: includeCA,
    });
  };

  // Pre-select topic if ID is provided in URL (e.g., from Syllabus page)
  useEffect(() => {
    if (topicFromUrl && !selectedTopic) {
      setSelectedTopic(topicFromUrl);
    }
  }, [topicFromUrl, selectedTopic]);

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Sparkles className="h-8 w-8 text-blue-600" />
          <h1 className="text-4xl font-bold">Generate Article</h1>
        </div>
        <p className="text-gray-600">
          Select a topic and generate an AI-powered article using RAG
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Topic Selection */}
        <Card>
          <CardHeader>
            <CardTitle>1. Select Topic</CardTitle>
          </CardHeader>
          <CardContent>
            <TopicSelector
              onSelectTopic={setSelectedTopic}
              selectedTopicId={selectedTopic?.id}
            />
          </CardContent>
        </Card>

        {/* Generation Options */}
        <Card>
          <CardHeader>
            <CardTitle>2. Generation Options</CardTitle>
          </CardHeader>
          <CardContent>
            {selectedTopic ? (
              <div className="space-y-6">
                {/* CA Toggle */}
                <div>
                  <div className="flex items-center gap-2">
                    <Switch
                      id="include-ca"
                      checked={includeCA}
                      onCheckedChange={setIncludeCA}
                      disabled={generateMutation.isPending}
                    />
                    <Label
                      htmlFor="include-ca"
                      className="flex items-center gap-2 cursor-pointer font-medium"
                    >
                      <Newspaper className="h-4 w-4 text-blue-600" />
                      Include Current Affairs (last 30 days)
                    </Label>
                  </div>
                  <p className="text-sm text-gray-600 mt-2 ml-12">
                    {includeCA
                      ? "✓ Article will include recent news and updates related to this topic"
                      : "× Article will only use textbook content (NCERT)"}
                  </p>
                </div>

                {/* Progress Bar */}
                <GenerationProgress
                  isGenerating={generateMutation.isPending}
                  progress={Math.min(progress, 100)}
                />

                {/* Error Block */}
                {generateMutation.isError && (
                  <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                    <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                    <div>
                      <p className="font-medium">Generation failed</p>
                      <p className="text-red-600 mt-0.5">
                        {(() => {
                          const axiosError =
                            generateMutation.error as AxiosError<ApiError>;
                          return (
                            axiosError.response?.data?.error ||
                            axiosError.response?.data?.message ||
                            "Could not generate article. Please try again."
                          );
                        })()}
                      </p>
                    </div>
                  </div>
                )}

                {/* Generate Button */}
                <Button
                  onClick={handleGenerate}
                  disabled={!selectedTopicId || generateMutation.isPending}
                  size="lg"
                  className="w-full"
                >
                  {generateMutation.isPending
                    ? "Generating..."
                    : "Generate Article"}
                </Button>
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                Select a topic to continue
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function GeneratePage() {
  return (
    <Suspense
      fallback={
        <div className="container mx-auto px-4 py-8 text-center text-gray-500">
          Loading generation tools...
        </div>
      }
    >
      <GeneratePageContent />
    </Suspense>
  );
}
