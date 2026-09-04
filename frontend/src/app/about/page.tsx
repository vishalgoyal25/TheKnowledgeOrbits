/**
 * About — server component (G2).
 *
 * Converted from "use client": the page had no state, effects or handlers, so
 * the directive was cost with no benefit. Being a server component is also what
 * lets it export `metadata`, which G3's SEO work needs.
 *
 * Content is unchanged word for word. What changed is the visual language:
 * one hero, one radius, tokens instead of hardcoded slate/blue/emerald, and
 * calmer type weights (font-black -> font-semibold).
 */
import type { Metadata } from "next";
import Link from "next/link";
import {
  Target,
  Zap,
  ShieldCheck,
  Users,
  BookOpen,
  Cpu,
  Globe,
  ArrowRight,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHero } from "@/components/shared/page-hero";
import { Section } from "@/components/shared/section";
import { ContentCard } from "@/components/shared/content-card";

export const metadata: Metadata = {
  title: "About | TheKnowledgeOrbits",
  description:
    "TheKnowledgeOrbits was born out of a simple observation: UPSC preparation shouldn't be about who has the most heavy books, but who has the most efficient access to distilled, syllabus-mapped knowledge.",
};

const PILLARS = [
  {
    title: "Accuracy First",
    desc: "We prioritize factual integrity over creative writing. Our AI is tuned to provide references and source-backed insights.",
    icon: ShieldCheck,
  },
  {
    title: "Community Driven",
    desc: "Knowledge grows when shared. Our users contribute to a global pool of orbits that help everyone learn better.",
    icon: Users,
  },
  {
    title: "Scalable IQ",
    desc: "As the UPSC pattern evolves, our platform evolves. We integrate daily Current Affairs into the core static syllabus.",
    icon: Globe,
  },
];

const APPROACH = [
  {
    icon: Target,
    title: "Retrieval Augmented Generation (RAG)",
    desc: "Our proprietary AI doesn't just guess. It retrieves data from verified NCERT, Yojna, and Standard textbooks before generating your study material.",
  },
  {
    icon: Zap,
    title: "Instant Syllabus Mapping",
    desc: 'Every word you read on our platform is tagged to a specific UPSC Syllabus pillar. No more "general" studies; only "targeted" excellence.',
  },
];

export default function AboutPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <PageHero
        eyebrow="Our mission"
        title={
          <>
            Democratizing excellence with{" "}
            <span className="text-primary">AI-powered intelligence</span>
          </>
        }
        description="TheKnowledgeOrbits was born out of a simple observation: UPSC preparation shouldn't be about who has the most heavy books, but who has the most efficient access to distilled, syllabus-mapped knowledge."
      />

      <Section>
        <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-2 lg:gap-14">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
              The preparation{" "}
              <span className="text-primary">paradigm shift</span>
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-muted-foreground sm:text-base">
              In a world of information overload, conventional coaching often
              leaves aspirants drowning in generic PDFs. We believe in{" "}
              <strong className="font-semibold text-foreground">
                Precision Learning
              </strong>
              .
            </p>

            <div className="mt-6 space-y-4">
              {APPROACH.map((item) => (
                <ContentCard key={item.title} tone="muted">
                  <div className="flex gap-4">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                      <item.icon className="h-5 w-5 text-primary" />
                    </span>
                    <div className="min-w-0">
                      <h3 className="mb-1 text-sm font-semibold text-foreground">
                        {item.title}
                      </h3>
                      <p className="text-sm leading-relaxed text-muted-foreground">
                        {item.desc}
                      </p>
                    </div>
                  </div>
                </ContentCard>
              ))}
            </div>
          </div>

          <ContentCard tone="muted" className="p-8 sm:p-10">
            <div className="flex flex-col items-center gap-5 text-center">
              <span className="flex h-20 w-20 items-center justify-center rounded-lg bg-card">
                <Cpu className="h-10 w-10 text-primary" />
              </span>
              <h3 className="text-lg font-semibold text-foreground">
                Your private knowledge cloud
              </h3>
              <p className="text-sm text-muted-foreground">
                Synced across all your devices.
              </p>
            </div>
          </ContentCard>
        </div>
      </Section>

      <Section tone="muted" className="border-y border-border">
        <div className="mb-8 text-center">
          <Badge variant="secondary" className="mb-3">
            Our foundations
          </Badge>
          <h2 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
            Built on three orbits
          </h2>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {PILLARS.map((pillar) => (
            <ContentCard key={pillar.title} className="p-6">
              <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                <pillar.icon className="h-6 w-6 text-primary" />
              </span>
              <h3 className="mb-2 text-base font-semibold text-foreground">
                {pillar.title}
              </h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {pillar.desc}
              </p>
            </ContentCard>
          ))}
        </div>
      </Section>

      <Section>
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
            A future without{" "}
            <span className="text-primary">expensive barriers</span>
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground sm:text-base">
            We envision a world where the daughter of a farmer in a remote
            village has the same quality of UPSC mentoring as someone in Old
            Rajinder Nagar. AI makes this equality possible.
          </p>
          <div className="mt-8">
            <Button asChild size="lg" className="group gap-2">
              <Link href="/auth/register">
                Be Part of the Revolution
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>
          </div>
        </div>
      </Section>

      <Section tone="muted" className="border-t border-border py-8 sm:py-10">
        <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
          <div className="flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-primary" />
            <span className="text-lg font-semibold tracking-tight text-foreground">
              TheKnowledgeOrbits
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            © 2026 AI-Powered UPSC Ecosystem. Built for the brilliant.
          </p>
        </div>
      </Section>
    </div>
  );
}
