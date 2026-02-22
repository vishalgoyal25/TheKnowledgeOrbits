"use client";

import React from "react";
import {
  Sparkles,
  Target,
  Zap,
  ShieldCheck,
  Users,
  Cpu,
  Search,
  Globe,
  ArrowRight,
  BookOpen,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function AboutPage() {
  return (
    <div className="flex flex-col min-h-screen bg-white">
      {/* 1. HERO SECTION: The Mission */}
      <section className="relative pt-20 pb-32 overflow-hidden bg-slate-900 text-white">
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-0 -left-1/4 w-1/2 h-1/2 bg-blue-500 rounded-full blur-[120px]" />
          <div className="absolute bottom-0 -right-1/4 w-1/2 h-1/2 bg-indigo-500 rounded-full blur-[120px]" />
        </div>

        <div className="container relative mx-auto px-4 text-center">
          <Badge className="mb-6 px-4 py-1 bg-white/10 text-blue-300 border-blue-500/30 backdrop-blur-sm">
            OUR MISSION
          </Badge>
          <h1 className="text-4xl md:text-6xl font-black mb-8 leading-tight tracking-tight">
            Democratizing Excellence <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">
              With AI-Powered Intelligence
            </span>
          </h1>
          <p className="text-xl text-slate-300 max-w-3xl mx-auto leading-relaxed font-medium">
            TheKnowledgeOrbits was born out of a simple observation: UPSC
            preparation shouldn't be about who has the most heavy books, but who
            has the most efficient access to distilled, syllabus-mapped
            knowledge.
          </p>
        </div>
      </section>

      {/* 2. THE PROBLEM & SOLUTION */}
      <section className="py-24 bg-white">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div className="space-y-8">
              <h2 className="text-4xl font-extrabold text-slate-900 tracking-tight">
                The Preparation <br />
                <span className="text-blue-600">Paradigm Shift</span>
              </h2>
              <p className="text-lg text-slate-600 leading-relaxed">
                In a world of information overload, conventional coaching often
                leaves aspirants drowning in generic PDFs. We believe in{" "}
                <strong>Precision Learning</strong>.
              </p>
              <div className="space-y-6">
                <div className="flex gap-4 p-5 rounded-2xl bg-blue-50 border border-blue-100">
                  <div className="h-10 w-10 bg-blue-600 rounded-xl flex items-center justify-center shrink-0">
                    <Target className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 mb-1">
                      Retrieval Augmented Generation (RAG)
                    </h4>
                    <p className="text-sm text-slate-600">
                      Our proprietary AI doesn't just guess. It retrieves data
                      from verified NCERT, Yojna, and Standard textbooks before
                      generating your study material.
                    </p>
                  </div>
                </div>
                <div className="flex gap-4 p-5 rounded-2xl bg-emerald-50 border border-emerald-100">
                  <div className="h-10 w-10 bg-emerald-600 rounded-xl flex items-center justify-center shrink-0">
                    <Zap className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 mb-1">
                      Instant Syllabus Mapping
                    </h4>
                    <p className="text-sm text-slate-600">
                      Every word you read on our platform is tagged to a
                      specific UPSC Syllabus pillar. No more "general" studies;
                      only "targeted" excellence.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="relative">
              <div className="aspect-square rounded-3xl bg-slate-100 p-8 flex items-center justify-center overflow-hidden border border-slate-200">
                <div className="relative z-10 text-center space-y-6">
                  <div className="h-24 w-24 bg-white rounded-3xl shadow-xl flex items-center justify-center mx-auto">
                    <Cpu className="h-12 w-12 text-blue-600 animate-pulse" />
                  </div>
                  <h3 className="text-2xl font-black text-slate-900">
                    Your Private <br /> Knowledge Cloud
                  </h3>
                  <p className="text-slate-500 font-medium">
                    Synced across all your devices.
                  </p>
                </div>
                {/* Decorative Elements */}
                <div className="absolute top-10 left-10 w-20 h-20 bg-blue-400/10 rounded-full blur-2xl" />
                <div className="absolute bottom-10 right-10 w-32 h-32 bg-indigo-400/10 rounded-full blur-2xl" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. CORE PILLARS */}
      <section className="py-24 bg-slate-50 border-y border-slate-100">
        <div className="container mx-auto px-4 text-center mb-16">
          <Badge className="bg-blue-100 text-blue-600 border-none mb-4">
            OUR FOUNDATIONS
          </Badge>
          <h2 className="text-4xl font-extrabold text-slate-900">
            Built on Three Orbits
          </h2>
        </div>

        <div className="container mx-auto px-4 grid grid-cols-1 md:grid-cols-3 gap-8">
          {[
            {
              title: "Accuracy First",
              desc: "We prioritize factual integrity over creative writing. Our AI is tuned to provide references and source-backed insights.",
              icon: ShieldCheck,
              color: "text-blue-600",
              bg: "bg-blue-100",
            },
            {
              title: "Community Driven",
              desc: "Knowledge grows when shared. Our users contribute to a global pool of orbits that help everyone learn better.",
              icon: Users,
              color: "text-purple-600",
              bg: "bg-purple-100",
            },
            {
              title: "Scalable IQ",
              desc: "As the UPSC pattern evolves, our platform evolves. We integrate daily Current Affairs into the core static syllabus.",
              icon: Globe,
              color: "text-emerald-600",
              bg: "bg-emerald-100",
            },
          ].map((pillar, i) => (
            <div
              key={i}
              className="p-8 bg-white rounded-3xl border border-slate-100 shadow-sm hover:shadow-xl transition-all hover:-translate-y-2"
            >
              <div
                className={`h-14 w-14 ${pillar.bg} rounded-2xl flex items-center justify-center mb-6`}
              >
                <pillar.icon className={`h-7 w-7 ${pillar.color}`} />
              </div>
              <h3 className="text-xl font-black text-slate-900 mb-4">
                {pillar.title}
              </h3>
              <p className="text-slate-600 leading-relaxed font-medium text-sm">
                {pillar.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* 4. THE DREAM: MISSION ROADMAP (Re-using some branding) */}
      <section className="py-32 bg-white relative overflow-hidden">
        <div className="container mx-auto px-4 text-center">
          <div className="max-w-2xl mx-auto space-y-8">
            <h2 className="text-4xl md:text-5xl font-black text-slate-900 tracking-tight">
              A Future Without <br />
              <span className="text-blue-600">Expensive Barriers</span>
            </h2>
            <p className="text-lg text-slate-600 font-medium leading-relaxed">
              We envision a world where the daughter of a farmer in a remote
              village has the same quality of UPSC mentoring as someone in Old
              Rajinder Nagar. AI makes this equality possible.
            </p>
            <div className="pt-8">
              <Link href="/auth/register">
                <Button
                  size="lg"
                  className="h-16 px-10 text-lg bg-blue-600 hover:bg-blue-700 gap-3 group"
                >
                  Be Part of the Revolution{" "}
                  <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER CTA */}
      <section className="py-16 bg-slate-900 border-t border-white/5">
        <div className="container mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-8">
          <div className="flex items-center gap-3">
            <BookOpen className="h-8 w-8 text-blue-500" />
            <span className="text-2xl font-bold text-white tracking-tighter">
              TheKnowledgeOrbits
            </span>
          </div>
          <p className="text-slate-400 text-sm font-medium">
            © 2026 AI-Powered UPSC Ecosystem. Built for the brilliant.
          </p>
        </div>
      </section>
    </div>
  );
}
