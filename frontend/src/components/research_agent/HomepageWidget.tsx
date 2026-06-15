"use client";

/**
 * HomepageWidget — Research Agent entry card for the homepage hero section.
 *
 * Lives ABOVE the HeroLiveCA (Today's Current Affairs) panel on the right side.
 * Follows the same card pattern as HeroLiveCA and DailyQuizWidget.
 *
 * Zero API calls — purely navigational. Render backend may be sleeping;
 * the homepage must never stall waiting for it.
 *
 * Two interaction paths:
 *   1. Mini input + submit → /research_agent?q=<encoded_query>  (pre-fills textarea)
 *   2. "Open Research Agent" CTA → /research_agent              (empty, fresh start)
 */

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { FlaskConical, ArrowRight, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import VoiceInput from "@/components/research_agent/VoiceInput";

export function HomepageWidget() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  const handleVoiceTranscript = useCallback((text: string) => {
    setQuery((prev) => {
      const joined = prev.trim() ? `${prev.trim()} ${text}` : text;
      return joined.slice(0, 300);
    });
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) {
      router.push("/research_agent");
      return;
    }
    router.push(`/research_agent?q=${encodeURIComponent(q)}`);
  }

  return (
    <div className="rounded-2xl border border-blue-100 bg-white shadow-xl overflow-hidden">
      {/* Header bar — matches HeroLiveCA style, blue theme for Research Agent */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-500 px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-white" />
          <span className="text-white text-sm font-bold">
            AI Research Agent
          </span>
          <Badge className="bg-white/20 text-white border-transparent text-[10px] px-2 py-0.5 font-bold backdrop-blur-sm">
            NEW
          </Badge>
        </div>
        <Link
          href="/research_agent"
          className="text-blue-100 text-xs hover:text-white font-medium flex items-center gap-1 transition-colors"
        >
          Open <ArrowRight className="h-3 w-3" />
        </Link>
      </div>

      {/* Body */}
      <div className="px-5 py-4 space-y-4">
        {/* Tagline */}
        <p className="text-xs text-slate-500 leading-relaxed">
          Ask any UPSC question — an 8-agent AI pipeline researches, verifies,
          and streams a cited report in real time.
        </p>

        {/* Mini input */}
        <form onSubmit={handleSubmit}>
          <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 focus-within:border-blue-300 focus-within:bg-white transition-all">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value.slice(0, 300))}
              placeholder="Ask a research question…"
              className="flex-1 bg-transparent text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none"
            />
            <VoiceInput onTranscript={handleVoiceTranscript} />
            <button
              type="submit"
              aria-label="Start research"
              className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            >
              <Search className="h-3.5 w-3.5" />
            </button>
          </div>
        </form>
      </div>

      {/* Footer CTA */}
      <div className="border-t border-slate-100 bg-slate-50 px-5 py-3">
        <Link href="/research_agent">
          <Button
            size="sm"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white gap-2 group/btn shadow-sm text-xs h-9"
          >
            <FlaskConical className="h-3.5 w-3.5" />
            Start Deep Research
            <ArrowRight className="h-3.5 w-3.5 group-hover/btn:translate-x-0.5 transition-transform" />
          </Button>
        </Link>
      </div>
    </div>
  );
}
