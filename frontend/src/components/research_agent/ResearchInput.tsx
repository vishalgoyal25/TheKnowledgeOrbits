"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Loader2, Search } from "lucide-react";
import { useAuth } from "@/lib/hooks/use-auth";
import VoiceInput from "./VoiceInput";
import {
  submitResearchQuery,
  PUBLIC_DAILY_LIMIT,
} from "@/lib/api/research-agent";
import type {
  QueryCachedResponse,
  ResearchReport,
} from "@/types/research_agent";

const MAX_CHARS = 500;

export interface ResearchInputProps {
  onSessionStarted: (sessionId: string) => void;
  onCachedResult: (
    report: Omit<ResearchReport, "session_id" | "created_at">,
  ) => void;
  disabled?: boolean;
  // External query trigger: set by parent when HomepageWidget ?q= param or example chip is clicked.
  pendingQuery?: string;
}

export default function ResearchInput({
  onSessionStarted,
  onCachedResult,
  disabled = false,
  pendingQuery = "",
}: ResearchInputProps) {
  const { isAuthenticated } = useAuth();
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // Tracks last auto-submitted query to avoid re-submitting the same string on re-renders.
  const lastAutoSubmitRef = useRef<string>("");

  // When voice finishes, append its transcript to whatever is in the textarea.
  const handleVoiceTranscript = useCallback((text: string) => {
    setQuery((prev) => {
      const joined = prev.trim() ? `${prev.trim()} ${text}` : text;
      return joined.slice(0, MAX_CHARS);
    });
    textareaRef.current?.focus();
  }, []);

  // Core submit logic extracted so it can be called from both the form and auto-submit effect.
  const doSubmit = useCallback(
    async (trimmed: string) => {
      if (!trimmed || isLoading || disabled) return;

      setIsLoading(true);
      setError(null);

      try {
        const result = await submitResearchQuery(trimmed);

        if (result.cached) {
          onCachedResult((result as QueryCachedResponse).report);
          setIsLoading(false);
        } else {
          onSessionStarted(result.session_id);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        setError(
          err instanceof Error
            ? err.message
            : "Something went wrong. Please try again.",
        );
        setIsLoading(false);
      }
    },
    [isLoading, disabled, onCachedResult, onSessionStarted],
  );

  // Auto-submit when parent pushes a new pendingQuery (URL ?q= param or example chip click).
  useEffect(() => {
    const q = pendingQuery.trim().slice(0, MAX_CHARS);
    if (!q || q === lastAutoSubmitRef.current || isLoading || disabled) return;
    lastAutoSubmitRef.current = q;
    setQuery(q);
    const timer = setTimeout(() => doSubmit(q), 200);
    return () => clearTimeout(timer);
  }, [pendingQuery]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await doSubmit(query.trim());
  }

  const isSubmitDisabled = disabled || isLoading || query.trim().length === 0;

  return (
    <form onSubmit={handleSubmit} className="w-full">
      {/* Input card */}
      <div
        className={[
          "relative rounded-xl border bg-white shadow-sm transition-shadow",
          "focus-within:shadow-md focus-within:border-blue-300",
          disabled ? "opacity-60 border-gray-200" : "border-gray-200",
        ].join(" ")}
      >
        {/* Query textarea */}
        <textarea
          ref={textareaRef}
          value={query}
          onChange={(e) => setQuery(e.target.value.slice(0, MAX_CHARS))}
          onKeyDown={(e) => {
            // Enter submits; Shift+Enter inserts a newline.
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (!isSubmitDisabled)
                handleSubmit(e as unknown as React.FormEvent);
            }
          }}
          placeholder="Ask a research question… e.g. 'Explain the significance of the Panchayati Raj system in Indian democracy'"
          rows={3}
          disabled={disabled || isLoading}
          className={[
            "w-full resize-none rounded-t-xl px-4 pt-3 pb-2",
            "text-sm text-gray-800 placeholder:text-gray-400",
            "focus:outline-none bg-transparent disabled:cursor-not-allowed",
          ].join(" ")}
        />

        {/* Bottom bar: voice button · char count · submit */}
        <div className="flex items-center justify-between px-3 pb-3 pt-1 gap-2">
          <div className="flex items-center gap-3">
            <VoiceInput
              onTranscript={handleVoiceTranscript}
              disabled={disabled || isLoading}
            />
            <span
              className={[
                "text-[11px] tabular-nums select-none",
                query.length >= MAX_CHARS ? "text-red-500" : "text-gray-400",
              ].join(" ")}
            >
              {query.length}/{MAX_CHARS}
            </span>
          </div>

          <button
            type="submit"
            disabled={isSubmitDisabled}
            className={[
              "flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-sm font-medium",
              "transition-all duration-150",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2",
              isSubmitDisabled
                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 shadow-sm",
            ].join(" ")}
          >
            {isLoading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Search className="w-3.5 h-3.5" />
            )}
            <span>{isLoading ? "Researching…" : "Research"}</span>
          </button>
        </div>
      </div>

      {/* Guest rate-limit notice — hidden for authenticated users */}
      {!isAuthenticated && (
        <p className="mt-1.5 text-[11px] text-gray-400 text-center">
          {PUBLIC_DAILY_LIMIT} free queries/day ·{" "}
          <a
            href="/login"
            className="underline hover:text-gray-600 transition-colors"
          >
            Sign in
          </a>{" "}
          for unlimited research + history
        </p>
      )}

      {/* Submission error */}
      {error && (
        <p role="alert" className="mt-2 text-xs text-red-600 text-center">
          {error}
        </p>
      )}
    </form>
  );
}
