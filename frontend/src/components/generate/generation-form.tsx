/**
 * Article generation form component
 */

'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useGenerateArticle } from '@/lib/hooks/use-article';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Sparkles, CheckCircle, AlertCircle } from 'lucide-react';

interface GenerationFormProps {
  topicId: string;
  topicName: string;
}

export default function GenerationForm({ topicId, topicName }: GenerationFormProps) {
  const router = useRouter();
  const [includeCA, setIncludeCA] = useState(false);

  const { mutate: generateArticle, isPending, isSuccess, isError, error, data } = useGenerateArticle();

  const handleGenerate = () => {
    generateArticle(
      { topic_id: topicId, include_ca: includeCA },
      {
        onSuccess: (data) => {
          // Redirect to article after 2 seconds
          setTimeout(() => {
            router.push(`/articles/${data.article.id}`);
          }, 2000);
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      {/* Topic Info */}
      <div className="bg-blue-50 rounded-lg p-4">
        <h3 className="font-semibold mb-1">Generating article for:</h3>
        <p className="text-gray-700">{topicName}</p>
      </div>

      {/* Options */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="include-ca">Include Current Affairs</Label>
            <p className="text-sm text-gray-500">
              Integrate recent news and developments
            </p>
          </div>
          <Switch
            id="include-ca"
            checked={includeCA}
            onCheckedChange={setIncludeCA}
            disabled={isPending}
          />
        </div>
      </div>

      {/* Status Messages */}
      {isPending && (
        <Alert>
          <Loader2 className="h-4 w-4 animate-spin" />
          <AlertDescription>
            Generating article... This may take 20-30 seconds.
          </AlertDescription>
        </Alert>
      )}

      {isSuccess && data && (
        <Alert className="bg-green-50 border-green-200">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">
            Article generated successfully! Redirecting...
            <div className="mt-2 text-sm">
              <p>Word count: {data.metadata.word_count}</p>
              <p>Quality score: {data.metadata.quality_score.toFixed(0)}%</p>
              <p>Sources used: {data.metadata.source_chunks}</p>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {isError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {error instanceof Error ? error.message : 'Failed to generate article'}
          </AlertDescription>
        </Alert>
      )}

      {/* Generate Button */}
      <Button
        onClick={handleGenerate}
        disabled={isPending || isSuccess}
        className="w-full gap-2"
        size="lg"
      >
        {isPending ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Generating...
          </>
        ) : isSuccess ? (
          <>
            <CheckCircle className="h-4 w-4" />
            Generated!
          </>
        ) : (
          <>
            <Sparkles className="h-4 w-4" />
            Generate Article
          </>
        )}
      </Button>
    </div>
  );
}
