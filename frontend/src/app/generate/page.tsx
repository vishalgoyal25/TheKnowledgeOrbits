'use client';

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { useTopic } from '@/lib/hooks/use-topics';
import { Topic } from '@/lib/types';
import TopicSelector from '@/components/generate/topic-selector';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useGenerateArticle } from '@/lib/hooks/use-article-generation';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Sparkles, Newspaper } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function GeneratePage() {
  const [includeCA, setIncludeCA] = useState(true); // 🆕 CA toggle state
  const searchParams = useSearchParams();
  const topicIdFromUrl = searchParams.get('topic_id');

  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null);

  // If topic_id in URL, fetch that topic
  const { data: topicFromUrl } = useTopic(topicIdFromUrl);

  // Create hooks
  const generateMutation = useGenerateArticle();
  const selectedTopicId = selectedTopic?.id;

  const handleGenerate = () => {
    if (!selectedTopicId) return;

    generateMutation.mutate({
      topic_id: selectedTopicId,
      include_ca: includeCA, // 🆕 Pass CA flag
    });
  };

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
                {/* 🆕 CA Toggle */}
                <div>
                  <div className="flex items-center gap-2">
                    <Switch
                      id="include-ca"
                      checked={includeCA}
                      onCheckedChange={setIncludeCA}
                    />
                    <Label htmlFor="include-ca" className="flex items-center gap-2 cursor-pointer font-medium">
                      <Newspaper className="h-4 w-4 text-blue-600" />
                      Include Current Affairs (last 30 days)
                    </Label>
                  </div>
                  <p className="text-sm text-gray-600 mt-2 ml-12">
                    {includeCA
                      ? '✓ Article will include recent news and updates related to this topic'
                      : '× Article will only use textbook content (NCERT)'}
                  </p>
                </div>

                {/* Generate Button */}
                <Button
                  onClick={handleGenerate}
                  disabled={!selectedTopicId || generateMutation.isPending}
                  size="lg"
                  className="w-full"
                >
                  {generateMutation.isPending ? 'Generating...' : 'Generate Article'}
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
