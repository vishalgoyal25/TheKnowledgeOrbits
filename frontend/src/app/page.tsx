/**
 * Advanced, High-Aesthetic Home Page (Light Theme Edition)
 *
 * Featuring dynamic Hero, Featured Articles via RAG, Ecosystem showcase,
 * and Roadmap for future UPSC features.
 */

"use client";

import Link from "next/link";
import { useArticles } from "@/lib/hooks/use-article";
import { Button } from "@/components/ui/button";
import ArticleCard from "@/components/articles/article-card";
import {
  Sparkles,
  Zap,
  FileQuestion,
  ArrowRight,
  Newspaper,
  BookMarked,
  Bookmark,
  CheckCircle2,
  PenTool,
  Users,
  ShieldCheck,
  Trophy,
  Lightbulb,
  Search,
  LayoutDashboard,
  Folder,
} from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { useSidebar } from "@/components/providers/sidebar-provider";
import { cn } from "@/lib/utils";

export default function HomePage() {
  const { data: articlesData, isLoading } = useArticles({ page_size: 9 });
  const articlesArray = Array.isArray(articlesData)
    ? articlesData
    : (articlesData as any)?.results || [];
  const articles = articlesArray.slice(0, 9);
  const { isCollapsed } = useSidebar();

  return (
    <div className="flex flex-col min-h-screen bg-white">
      {/*
          WRAPPER FOR TOP SECTIONS (Pushed by Sidebar)
          Only applies padding for the sections within the sidebar's typical reach.
      */}
      <div
        className={cn(
          "transition-all duration-300 ease-in-out",
          isCollapsed ? "lg:pl-20" : "lg:pl-64",
        )}
      >
        {/* 1. HERO SECTION: Light with subtle gradient */}
        <section className="relative overflow-hidden pt-24 pb-32 lg:pt-32 lg:pb-48 bg-gradient-to-b from-blue-50 to-white border-b">
          {/* ... existing hero content ... */}
          <div className="container relative mx-auto px-4 text-center">
            <Badge className="mb-6 px-4 py-1.5 bg-blue-100 text-blue-600 border-blue-200 hover:bg-blue-200 transition-all cursor-default shadow-sm border">
              <Sparkles className="h-3.5 w-3.5 mr-2" />
              Empowering UPSC Aspirants with AI-RAG Technology
            </Badge>

            <h1 className="text-5xl md:text-7xl font-extrabold text-slate-900 tracking-tight mb-8">
              Your Personal AI <br />
              <span className="text-blue-600">Syllabus Maestro</span>
            </h1>

            <p className="text-xl text-slate-600 mb-12 max-w-3xl mx-auto leading-relaxed">
              Move beyond generic study material. Harness the power of
              <span className="text-slate-900 font-semibold">
                {" "}
                Retrieval Augmented Generation
              </span>{" "}
              to create syllabus-mapped articles from verified NCERT & Current
              Affairs sources instantly.
            </p>

            <div className="flex flex-wrap gap-4 justify-center items-center">
              <Link href="/generate">
                <Button
                  size="lg"
                  className="h-14 px-8 text-lg bg-blue-600 hover:bg-blue-700 shadow-xl shadow-blue-950/10 gap-3 group"
                >
                  <Sparkles className="h-5 w-5 group-hover:rotate-12 transition-transform" />
                  Generate AI Article
                </Button>
              </Link>

              <Link href="/assessment">
                <Button
                  size="lg"
                  variant="outline"
                  className="h-14 px-8 text-lg text-slate-700 border-slate-200 bg-white hover:bg-slate-50 gap-3"
                >
                  <FileQuestion className="h-5 w-5" />
                  Try Interactive Quiz
                </Button>
              </Link>
            </div>

            <div className="mt-16 flex items-center justify-center gap-8 opacity-70">
              <div className="flex flex-col items-center gap-1">
                <span className="text-2xl font-bold text-slate-900">100%</span>
                <span className="text-xs text-slate-500 uppercase tracking-widest font-bold">
                  Syllabus Coverage
                </span>
              </div>
              <div className="w-px h-8 bg-slate-200" />
              <div className="flex flex-col items-center gap-1">
                <span className="text-2xl font-bold text-slate-900">
                  Verified
                </span>
                <span className="text-xs text-slate-500 uppercase tracking-widest font-bold">
                  NCERT Sources
                </span>
              </div>
              <div className="w-px h-8 bg-slate-200" />
              <div className="flex flex-col items-center gap-1">
                <span className="text-2xl font-bold text-slate-900">Daily</span>
                <span className="text-xs text-slate-500 uppercase tracking-widest font-bold">
                  CA Integration
                </span>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* 2. RECENT CONTRIBUTIONS: Actual functional data */}
      <section className="py-24 bg-slate-50/50">
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row items-baseline justify-between mb-12 gap-4">
            <div>
              <h2 className="text-3xl font-bold text-slate-900 mb-2">
                Latest Knowledge Orbits
              </h2>
              <p className="text-slate-600">
                Freshly generated articles by our community and AI.
              </p>
            </div>
            <Link
              href="/articles"
              className="flex items-center text-blue-600 font-bold hover:gap-2 transition-all"
            >
              View All Insights <ArrowRight className="h-4 w-4 ml-2" />
            </Link>
          </div>

          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => (
                <Skeleton
                  key={i}
                  className="h-[300px] w-full rounded-2xl bg-white shadow-sm"
                />
              ))}
            </div>
          ) : articles.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {articles.map((article: any) => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          ) : (
            <div className="text-center py-20 bg-white border-2 border-dashed border-slate-200 rounded-3xl">
              <Lightbulb className="h-12 w-12 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500 font-medium">
                No articles yet. Be the first to orbit!
              </p>
              <Link
                href="/generate"
                className="mt-4 block text-blue-600 font-bold hover:underline"
              >
                Start Generating →
              </Link>
            </div>
          )}
        </div>
      </section>

      {/* 3. PLATFORM CORE FEATURES: Luring and Informative */}
      <section className="py-24 bg-white border-y border-slate-100">
        <div className="container mx-auto px-4 text-center mb-16">
          <h2 className="text-4xl font-extrabold text-slate-900 mb-6">
            The All-in-One UPSC OS
          </h2>
          <p className="text-slate-600 max-w-2xl mx-auto">
            We don't just provide material; we provide an ecosystem that evolves
            with your preparation needs.
          </p>
        </div>

        <div className="container mx-auto px-4 grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Feature 1 */}
          <div className="p-8 rounded-2xl bg-slate-50/50 border border-slate-100 transition-all hover:bg-white hover:shadow-2xl hover:shadow-slate-200/50 hover:-translate-y-1">
            <div className="h-12 w-12 bg-blue-100 rounded-2xl flex items-center justify-center mb-6">
              <BookMarked className="h-6 w-6 text-blue-600" />
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-3">
              Sync-Notebook
            </h3>
            <p className="text-sm text-slate-600 mb-6 font-medium leading-relaxed">
              Save any generated article instantly to your personalized
              dashboard. Highlight, annotate, and review your progress over
              time.
            </p>
            <Link
              href="/notebook"
              className="text-blue-600 text-sm font-bold flex items-center gap-1 group"
            >
              Open Notebook{" "}
              <ArrowRight className="h-3 w-3 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>

          {/* Feature 2 */}
          <div className="p-8 rounded-2xl bg-slate-50/50 border border-slate-100 transition-all hover:bg-white hover:shadow-2xl hover:shadow-slate-200/50 hover:-translate-y-1">
            <div className="h-12 w-12 bg-emerald-100 rounded-2xl flex items-center justify-center mb-6">
              <Zap className="h-6 w-6 text-emerald-600" />
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-3">
              Smart-Recall Quizzes
            </h3>
            <p className="text-sm text-slate-600 mb-6 font-medium leading-relaxed">
              Every article comes with a RAG-powered quiz. Don't just
              read—verify your understanding with syllabus-mapped questions.
            </p>
            <Link
              href="/assessment"
              className="text-emerald-600 text-sm font-bold flex items-center gap-1 group"
            >
              Start Practice{" "}
              <ArrowRight className="h-3 w-3 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>

          {/* Feature 3 */}
          <div className="p-8 rounded-2xl bg-slate-50/50 border border-slate-100 transition-all hover:bg-white hover:shadow-2xl hover:shadow-slate-200/50 hover:-translate-y-1">
            <div className="h-12 w-12 bg-purple-100 rounded-2xl flex items-center justify-center mb-6">
              <Search className="h-6 w-6 text-purple-600" />
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-3">
              Syllabus Mapping
            </h3>
            <p className="text-sm text-slate-600 mb-6 font-medium leading-relaxed">
              No more irrelevant topics. Every insight is tagged to specific
              UPSC pillars (Polity, History, Ethics, etc.) to keep you focused.
            </p>
            <Link
              href="/topics"
              className="text-purple-600 text-sm font-bold flex items-center gap-1 group"
            >
              Explore Pillars{" "}
              <ArrowRight className="h-3 w-3 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>
      </section>

      {/* 4. THE FUTURE: MISSION ROADMAP (Light Theme) */}
      <section className="py-24 bg-blue-50/30 overflow-hidden relative">
        <div className="container relative mx-auto px-4">
          <div className="flex flex-col lg:flex-row items-center gap-16">
            <div className="lg:w-1/2">
              <Badge className="bg-blue-100 text-blue-600 border-none mb-6">
                BEYOND GENERATION
              </Badge>
              <h2 className="text-4xl font-bold text-slate-900 mb-8 leading-tight">
                Complete UPSC Mastery with <br />
                AI Ecosystem
              </h2>
              <p className="text-lg text-slate-600 mb-10 leading-relaxed">
                We are building the future of UPSC preparation. Our upcoming
                modules will provide a full-spectrum solution from Prelims to
                Interview.
              </p>

              <div className="space-y-6">
                <div className="flex gap-4 p-4 rounded-xl bg-white border border-slate-100 shadow-sm transition-all hover:shadow-md">
                  <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center shrink-0">
                    <PenTool className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 flex items-center gap-2">
                      Mains Answer Evaluation{" "}
                      <Badge
                        variant="outline"
                        className="text-[10px] h-4 text-blue-600 border-blue-600"
                      >
                        COMING SOON
                      </Badge>
                    </h4>
                    <p className="text-sm text-slate-500">
                      Submit your hand-written answers; our AI evaluates them
                      based on UPSC parameters like Structure, Content, and
                      Relevance.
                    </p>
                  </div>
                </div>

                <div className="flex gap-4 p-4 rounded-xl bg-white border border-slate-100 shadow-sm transition-all hover:shadow-md">
                  <div className="h-10 w-10 rounded-lg bg-emerald-100 flex items-center justify-center shrink-0">
                    <Trophy className="h-5 w-5 text-emerald-600" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 flex items-center gap-2">
                      All-India Test Series{" "}
                      <Badge
                        variant="outline"
                        className="text-[10px] h-4 text-emerald-600 border-emerald-600"
                      >
                        Q2 2026
                      </Badge>
                    </h4>
                    <p className="text-sm text-slate-500">
                      Compete with thousands. Get AI-powered bottleneck analysis
                      to find which subjects are holding back your Prelims
                      score.
                    </p>
                  </div>
                </div>

                <div className="flex gap-4 p-4 rounded-xl bg-white border border-slate-100 shadow-sm transition-all hover:shadow-md">
                  <div className="h-10 w-10 rounded-lg bg-indigo-100 flex items-center justify-center shrink-0">
                    <Users className="h-5 w-5 text-indigo-600" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 flex items-center gap-2">
                      AI Interview Mentor{" "}
                      <Badge
                        variant="outline"
                        className="text-[10px] h-4 text-indigo-600 border-indigo-600"
                      >
                        Q3 2026
                      </Badge>
                    </h4>
                    <p className="text-sm text-slate-500">
                      Personalized mock interviews based on your DAF, with
                      instant feedback on tone, body language, and content
                      depth.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="lg:w-1/2 relative w-full">
              <div className="p-10 rounded-3xl bg-white border border-slate-100 shadow-2xl space-y-8">
                <h3 className="text-2xl font-bold text-slate-900">Why wait?</h3>
                <p className="text-slate-600 leading-relaxed">
                  Start building your knowledge base today and be the first to
                  access our premium evaluation tools.
                </p>

                <ul className="space-y-4">
                  <li className="flex items-center gap-3 text-sm text-slate-700 font-medium font-medium">
                    <div className="bg-blue-100 p-1 rounded-full">
                      <CheckCircle2 className="h-4 w-4 text-blue-600" />
                    </div>{" "}
                    Verified UPSC Syllabus Mapping
                  </li>
                  <li className="flex items-center gap-3 text-sm text-slate-700 font-medium font-medium">
                    <div className="bg-blue-100 p-1 rounded-full">
                      <CheckCircle2 className="h-4 w-4 text-blue-600" />
                    </div>{" "}
                    Personal Notebook Sync
                  </li>
                  <li className="flex items-center gap-3 text-sm text-slate-700 font-medium font-medium">
                    <div className="bg-blue-100 p-1 rounded-full">
                      <CheckCircle2 className="h-4 w-4 text-blue-600" />
                    </div>{" "}
                    AI-powered Doubt Clearance
                  </li>
                  <li className="flex items-center gap-3 text-sm text-slate-700 font-medium font-medium">
                    <div className="bg-blue-100 p-1 rounded-full">
                      <CheckCircle2 className="h-4 w-4 text-blue-600" />
                    </div>{" "}
                    Detailed Performance Analytics
                  </li>
                </ul>

                <Button
                  size="lg"
                  asChild
                  className="w-full h-14 bg-slate-900 text-white hover:bg-slate-800 font-bold border-none transition-all shadow-lg shadow-slate-200"
                >
                  <Link href="/auth/register">Secure Early Access</Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 5. FINISH: Ecosystem Links (Functional Buttons) */}
      <section className="py-24 bg-white">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Link href="/dashboard" className="group">
              <div className="p-8 bg-slate-50 border border-slate-100 rounded-3xl transition-all hover:bg-white hover:shadow-2xl hover:shadow-blue-600/5 hover:border-blue-200">
                <LayoutDashboard className="h-8 w-8 text-blue-600 mb-6 group-hover:scale-110 transition-transform" />
                <h4 className="font-bold text-slate-900 text-lg">
                  Personal Dashboard
                </h4>
                <p className="text-sm text-slate-500 mt-2 leading-relaxed">
                  Track your entire UPSC journey in one place.
                </p>
              </div>
            </Link>

            <Link href="/current-affairs" className="group">
              <div className="p-8 bg-slate-50 border border-slate-100 rounded-3xl transition-all hover:bg-white hover:shadow-2xl hover:shadow-emerald-600/5 hover:border-emerald-200">
                <Newspaper className="h-8 w-8 text-emerald-600 mb-6 group-hover:scale-110 transition-transform" />
                <h4 className="font-bold text-slate-900 text-lg">
                  Daily Current Affairs
                </h4>
                <p className="text-sm text-slate-500 mt-2 leading-relaxed">
                  UPSC-centric news distilled for your prep.
                </p>
              </div>
            </Link>

            <Link href="/topics" className="group">
              <div className="p-8 bg-slate-50 border border-slate-100 rounded-3xl transition-all hover:bg-white hover:shadow-2xl hover:shadow-purple-600/5 hover:border-purple-200">
                <Folder className="h-8 w-8 text-purple-600 mb-6 group-hover:scale-110 transition-transform" />
                <h4 className="font-bold text-slate-900 text-lg">
                  Syllabus Explorer
                </h4>
                <p className="text-sm text-slate-500 mt-2 leading-relaxed">
                  Deep dive into every pillar of the exam.
                </p>
              </div>
            </Link>

            <Link href="/bookmarks" className="group">
              <div className="p-8 bg-slate-50 border border-slate-100 rounded-3xl transition-all hover:bg-white hover:shadow-2xl hover:shadow-pink-600/5 hover:border-pink-200">
                <Bookmark className="h-8 w-8 text-pink-600 mb-6 group-hover:scale-110 transition-transform" />
                <h4 className="font-bold text-slate-900 text-lg">
                  Saved Articles
                </h4>
                <p className="text-sm text-slate-500 mt-2 leading-relaxed">
                  Quickly access bits of gold you've discovered.
                </p>
              </div>
            </Link>
          </div>
        </div>
      </section>

      {/* 6. FAQ SECTION: For Clarity & Conversion */}
      <section id="faqs" className="py-24 bg-white border-t border-slate-100">
        <div className="container mx-auto px-4 max-w-4xl">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              Frequently Asked Questions
            </h2>
            <p className="text-slate-600">
              Everything you need to know about TheKnowledgeOrbits
            </p>
          </div>

          <Accordion type="single" collapsible className="w-full space-y-4">
            <AccordionItem
              value="item-1"
              className="border border-slate-200 rounded-2xl px-6 bg-slate-50/50"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-slate-800 text-left">
                How does TheKnowledgeOrbits help in UPSC preparation?
              </AccordionTrigger>
              <AccordionContent className="text-slate-600 leading-relaxed pb-6">
                TheKnowledgeOrbits is a specialized UPSC Operating System.
                Unlike random internet searches, we provide context-aware,
                syllabus-mapped articles generated using AI-RAG technology. It
                helps you quickly cover static topics and link them with current
                affairs, followed by instant quizzes for retention.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-2"
              className="border border-slate-200 rounded-2xl px-6 bg-slate-50/50"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-slate-800 text-left">
                What is RAG technology and why is it better?
              </AccordionTrigger>
              <AccordionContent className="text-slate-600 leading-relaxed pb-6">
                RAG (Retrieval-Augmented Generation) is our secret sauce.
                Instead of just "hallucinating" facts like standard AI, our
                system first fetches relevant data from multiple verified UPSC
                sources (NCERTs, PIB, Standard Textbooks) and then synthesizes
                an answer. This ensures 99% factual accuracy and relevance.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-3"
              className="border border-slate-200 rounded-2xl px-6 bg-slate-50/50"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-slate-800 text-left">
                Are the articles based strictly on the UPSC syllabus?
              </AccordionTrigger>
              <AccordionContent className="text-slate-600 leading-relaxed pb-6">
                Yes. Every article generated is tagged to specific GS pillars
                (GS 1-4) or Prelims subjects. Our AI is tuned to favor
                UPSC-style language and importance-weighting, ensuring you don't
                waste time on non-essential trivia.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-4"
              className="border border-slate-200 rounded-2xl px-6 bg-slate-50/50"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-slate-800 text-left">
                Can I really use this for Mains Answer Writing?
              </AccordionTrigger>
              <AccordionContent className="text-slate-600 leading-relaxed pb-6">
                Absolutely. The "Knowledge Orbits" you generate follow a
                structured format: Context, Key Dimensions, Impact, and
                Conclusion. These structure-bits reflect the standard framework
                required for Mains answers, helping you build a mental template
                for every topic.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-5"
              className="border border-slate-200 rounded-2xl px-6 bg-slate-50/50"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-slate-800 text-left">
                How frequently is the Current Affairs knowledge base updated?
              </AccordionTrigger>
              <AccordionContent className="text-slate-600 leading-relaxed pb-6">
                Our "Current Affairs Engine" scans major newspapers (The Hindu,
                Indian Express) and government sources (PIB, Sansad TV) daily.
                New insights are available to the AI within hours of their
                publication, keeping your knowledge fresh.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-6"
              className="border border-slate-200 rounded-2xl px-6 bg-slate-50/50"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-slate-800 text-left">
                What is the "Sync-Notebook" feature?
              </AccordionTrigger>
              <AccordionContent className="text-slate-600 leading-relaxed pb-6">
                Sync-Notebook is your digital library. Any article you generate
                can be saved with one click. These are stored securely on our
                cloud, allow you to highlight key points, and are indexed for
                quick searching during revision sessions.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-7"
              className="border border-slate-200 rounded-2xl px-6 bg-slate-50/50"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-slate-800 text-left">
                Do the quizzes cover previous year questions (PYQs)?
              </AccordionTrigger>
              <AccordionContent className="text-slate-600 leading-relaxed pb-6">
                While we focus on AI-generated questions mapped to your current
                reading, our system analysis logic includes PYQ patterns to
                ensure the difficulty and type of questions reflect actual UPSC
                trends.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="item-8"
              className="border border-slate-200 rounded-2xl px-6 bg-slate-50/50"
            >
              <AccordionTrigger className="hover:no-underline font-bold text-slate-800 text-left">
                Is the platform mobile-responsive?
              </AccordionTrigger>
              <AccordionContent className="text-slate-600 leading-relaxed pb-6">
                Yes. The platform is designed for cross-device usage. You can
                generate articles on your laptop and take quizzes on your phone
                while commuting.
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </section>

      {/* 7. TRUST & SECURITY: Final Assurance */}
      <section className="py-16 border-y border-slate-100 bg-slate-50/30">
        <div className="container mx-auto px-4 flex flex-wrap justify-center gap-12 items-center opacity-70 grayscale-0">
          <div className="flex items-center gap-2 text-slate-700">
            <ShieldCheck className="h-5 w-5 text-blue-600" />
            <span className="font-bold uppercase tracking-tighter text-sm">
              NCERT Verified
            </span>
          </div>
          <div className="flex items-center gap-2 text-slate-700">
            <ShieldCheck className="h-5 w-5 text-blue-600" />
            <span className="font-bold uppercase tracking-tighter text-sm">
              PIB & Hindu Sourced
            </span>
          </div>
          <div className="flex items-center gap-2 text-slate-700">
            <ShieldCheck className="h-5 w-5 text-blue-600" />
            <span className="font-bold uppercase tracking-tighter text-sm">
              Secure-Data-Notebook
            </span>
          </div>
          <div className="flex items-center gap-2 text-slate-700">
            <ShieldCheck className="h-5 w-5 text-blue-600" />
            <span className="font-bold uppercase tracking-tighter text-sm">
              AI-Powered Validation
            </span>
          </div>
        </div>
      </section>
    </div>
  );
}
