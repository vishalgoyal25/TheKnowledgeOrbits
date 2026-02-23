"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useGenerateQuiz } from "@/lib/hooks/use-quiz";
import { Topic, QuizGenerateRequest, ApiError } from "@/lib/types";
import { AxiosError } from "axios";
import TopicSelector from "@/components/generate/topic-selector";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Brain,
  Newspaper,
  Sparkles,
  AlertCircle,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { createLogger } from "@/lib/logger";

const logger = createLogger("QuizGenerator");

export default function QuizGeneratorPage() {
  const router = useRouter();
  const generateQuizMutation = useGenerateQuiz();

  // State
  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null);
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">(
    "medium",
  );
  const [questionCount, setQuestionCount] = useState<number>(10);
  const [includeCA, setIncludeCA] = useState<boolean>(false);

  const handleGenerate = () => {
    if (!selectedTopic) return;

    const request: QuizGenerateRequest = {
      topic_id: selectedTopic.id,
      difficulty,
      question_count: questionCount,
      include_ca: includeCA,
    };

    generateQuizMutation.mutate(request, {
      onSuccess: (quiz) => {
        router.push(`/assessment/${quiz.id}`);
      },
      onError: (error) => {
        logger.error("Quiz generation failed:", error);
      },
    });
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Header */}
      <div className="mb-8">
        <Link
          href="/assessment"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-primary mb-4 transition-colors"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Assessments
        </Link>
        <div className="flex items-center gap-3 mb-2">
          <Brain className="h-8 w-8 text-primary" />
          <h1 className="text-4xl font-bold tracking-tight">Create New Quiz</h1>
        </div>
        <p className="text-muted-foreground text-lg">
          Generate an AI-powered quiz tailored to your syllabus and difficulty
          level.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Topic Selection */}
        <div className="lg:col-span-7 space-y-6">
          <Card className="h-full border-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="bg-primary/10 text-primary w-8 h-8 rounded-full flex items-center justify-center text-sm">
                  1
                </span>
                Select Topic
              </CardTitle>
              <CardDescription>
                Choose the subject area for your quiz. Search by name or
                keyword.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <TopicSelector
                onSelectTopic={setSelectedTopic}
                selectedTopicId={selectedTopic?.id}
              />
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Configuration */}
        <div className="lg:col-span-5 space-y-6">
          <Card className="border-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="bg-primary/10 text-primary w-8 h-8 rounded-full flex items-center justify-center text-sm">
                  2
                </span>
                Configure Quiz
              </CardTitle>
              <CardDescription>
                Customize difficulty, length, and content mix.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-8">
              {/* Difficulty */}
              <div className="space-y-3">
                <Label>Difficulty Level</Label>
                <Select
                  value={difficulty}
                  onValueChange={(value: "easy" | "medium" | "hard") =>
                    setDifficulty(value)
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select difficulty" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="easy">
                      Easy (Conceptual & Direct)
                    </SelectItem>
                    <SelectItem value="medium">
                      Medium (Application Based)
                    </SelectItem>
                    <SelectItem value="hard">
                      Hard (Multi-statement & Analytic)
                    </SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {difficulty === "easy" &&
                    "Best for beginners. Focuses on definitions and direct facts."}
                  {difficulty === "medium" &&
                    "Balanced mix. Tests application of concepts."}
                  {difficulty === "hard" &&
                    "Exam simulation. Complex multi-statement questions."}
                </p>
              </div>

              {/* Question Count */}
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <Label>
                    Number of Questions:{" "}
                    <span className="font-bold text-primary">
                      {questionCount}
                    </span>
                  </Label>
                </div>
                <Slider
                  value={[questionCount]}
                  min={5}
                  max={20}
                  step={5}
                  onValueChange={(values) => setQuestionCount(values[0])}
                  className="py-2"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>5</span>
                  <span>10</span>
                  <span>15</span>
                  <span>20</span>
                </div>
              </div>

              {/* Current Affairs Toggle */}
              <div className="flex items-center justify-between space-x-2 border rounded-lg p-4 bg-muted/30">
                <div className="space-y-1">
                  <Label
                    htmlFor="ca-mode"
                    className="flex items-center gap-2 font-medium"
                  >
                    <Newspaper className="h-4 w-4 text-primary" />
                    Hybrid Mode
                  </Label>
                  <p className="text-xs text-muted-foreground">
                    Include recent Current Affairs questions related to this
                    topic.
                  </p>
                </div>
                <Switch
                  id="ca-mode"
                  checked={includeCA}
                  onCheckedChange={setIncludeCA}
                />
              </div>

              {/* Error Message */}
              {generateQuizMutation.isError && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Generation Failed</AlertTitle>
                  <AlertDescription>
                    {(() => {
                      const axiosError =
                        generateQuizMutation.error as AxiosError<ApiError>;
                      return (
                        axiosError.response?.data?.message ||
                        axiosError.response?.data?.error ||
                        "Something went wrong. Please try again."
                      );
                    })()}
                  </AlertDescription>
                </Alert>
              )}

              {/* Generate Button */}
              <Button
                size="lg"
                className="w-full gap-2 text-lg h-12"
                onClick={handleGenerate}
                disabled={!selectedTopic || generateQuizMutation.isPending}
              >
                {generateQuizMutation.isPending ? (
                  <>
                    <Sparkles className="h-5 w-5 animate-spin" />
                    Generating Quiz...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-5 w-5" />
                    Generate Quiz
                  </>
                )}
              </Button>

              {!selectedTopic && (
                <p className="text-xs text-center text-muted-foreground animate-pulse">
                  Please select a topic to continue
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
