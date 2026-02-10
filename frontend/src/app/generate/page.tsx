/**
 * Article generation page
 */

'use client';

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { useTopic } from '@/lib/hooks/use-topics';
import { Topic } from '@/lib/types';
import TopicSelector from '@/components/generate/topic-selector';
import GenerationForm from '@/components/generate/generation-form';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Sparkles } from 'lucide-react';

export default function GeneratePage() {
  const searchParams = useSearchParams();
  const topicIdFromUrl = searchParams.get('topic_id');
  
  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null);
  
  // If topic_id in URL, fetch that topic
  const { data: topicFromUrl } = useTopic(topicIdFromUrl);
  
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
              <GenerationForm
                topicId={selectedTopic.id}
                topicName={selectedTopic.name}
              />
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
