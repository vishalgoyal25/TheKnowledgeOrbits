import { Button } from "@/components/ui/button";
import { AlertTriangle, Mail, Scale } from "lucide-react";
import Link from "next/link";

export default function TermsOfService() {
  return (
    <div className="bg-slate-50 min-h-screen py-16">
      <div className="container mx-auto px-4 max-w-4xl">
        {/* Header */}
        <div className="bg-white rounded-3xl p-8 md:p-12 shadow-sm border border-slate-200 mb-8 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <Scale size={160} />
          </div>
          <div className="relative z-10 text-center md:text-left">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-blue-600 text-xs font-bold uppercase tracking-wider mb-4">
              <Scale className="h-3.5 w-3.5" /> Legal Framework
            </div>
            <h1 className="text-4xl md:text-5xl font-black text-slate-900 mb-4 tracking-tight">
              Terms of Service
            </h1>
            <p className="text-slate-500 font-medium text-lg max-w-2xl">
              Last Updated: February 25, 2026. Please read these terms carefully
              before using our platform.
            </p>
          </div>
        </div>

        {/* Hobby Project Disclaimer */}
        <div className="bg-amber-50 border-2 border-amber-200 rounded-2xl p-6 mb-10 flex flex-col md:flex-row gap-6 items-center">
          <div className="h-14 w-14 shrink-0 bg-amber-100 rounded-full flex items-center justify-center text-amber-600">
            <AlertTriangle className="h-8 w-8" />
          </div>
          <div>
            <h2 className="font-bold text-amber-900 uppercase text-sm tracking-widest mb-1">
              Important: Hobby & Educational Project Notice
            </h2>
            <p className="text-amber-800 text-sm leading-relaxed">
              TheKnowledgeOrbits is a{" "}
              <strong>personal, non-commercial hobby project</strong> developed
              for technical learning and experimental purposes, specifically
              focusing on RAG (Retrieval-Augmented Generation) and AI
              orchestration. This platform is not a corporate entity or a
              commercial service.
            </p>
          </div>
        </div>

        {/* Content */}
        <div className="bg-white rounded-3xl p-8 md:p-12 shadow-sm border border-slate-200 space-y-12 text-slate-700 leading-relaxed">
          {/* Section 1 */}
          <section>
            <h2 className="text-2xl font-black text-slate-900 mb-4">
              1. Project Intent & Scope
            </h2>
            <p className="mb-4">
              The primary objective of this project is a proof-of-concept for an
              AI-driven UPSC preparation operating system. It demonstrates the
              integration of modern web technologies, cloud infrastructure, and
              Large Language Models (LLMs) to automate knowledge synthesis.
            </p>
            <p>
              By using this site, you acknowledge that it is provided "as-is"
              for educational exploration and may contain experimental features.
            </p>
          </section>

          {/* Section 2 */}
          <section>
            <h2 className="text-2xl font-black text-slate-900 mb-4">
              2. Intellectual Property & Content Aggregation
            </h2>
            <p className="mb-4 font-bold text-slate-900 underline">
              Our Commitment to Copyright Integrity:
            </p>
            <p className="mb-4">
              We leverage Retrieval-Augmented Generation (RAG) to synthesize
              information. We do not intend to compete with or replace original
              news publishers. Our system follows these strict guidelines:
            </p>
            <ul className="list-disc pl-6 space-y-3">
              <li>
                <strong>Transformation:</strong> Original articles are used as
                raw data for AI inference to generate original educational
                outputs (summaries, quizzes, and insights).
              </li>
              <li>
                <strong>Attribution:</strong> Every piece of aggregated data is
                explicitly attributed to its original source (e.g., The Hindu,
                Indian Express, PIB).
              </li>
              <li>
                <strong>Non-Substitution:</strong> We only display short
                snippets (~300 characters) for context. Users are encouraged and
                directed to "View Original Source" to read the full coverage on
                the publisher&apos;s own site.
              </li>
              <li>
                <strong>Non-Commercial:</strong> This project is currently
                entirely free and non-monetized to comply with personal/academic
                dissemination clauses of most news publications.
              </li>
            </ul>
          </section>

          {/* Section 3 */}
          <section>
            <h2 className="text-2xl font-black text-slate-900 mb-4">
              3. User Conduct
            </h2>
            <p className="mb-4 text-slate-600">
              Users are granted a limited, revocable license to access the site
              for personal, non-commercial preparation for competitive exams.
              You agree not to:
            </p>
            <ul className="list-disc pl-6 space-y-3">
              <li>
                Use high-frequency automated tools to scrape our synthetic data.
              </li>
              <li>
                Portray the data as your own without acknowledging the original
                sources cited.
              </li>
              <li>
                Bypass any security measures implemented to protect the
                platform.
              </li>
            </ul>
          </section>

          {/* Section 4 */}
          <section>
            <h2 className="text-2xl font-black text-slate-900 mb-4">
              4. Take-Down Policy (DMCA / Copyright)
            </h2>
            <p className="mb-4">
              As a hobbyist project, we have the utmost respect for the
              intellectual property of others. If you are a copyright holder and
              believe your material has been used in a way that constitutes
              infringement beyond "Fair Use" or "Educational Dissemination,"
              please contact us at:
            </p>
            <div className="bg-slate-50 p-4 rounded-xl font-mono text-sm border border-slate-100 flex items-center gap-2">
              <Mail className="h-4 w-4 text-blue-500" />{" "}
              support@knowledgeorbits.com
            </div>
            <p className="mt-4 italic">
              We pledge to remove any disputed content within 48-72 hours of
              receiving a valid verified request.
            </p>
          </section>

          {/* Section 5 */}
          <section>
            <h2 className="text-2xl font-black text-slate-900 mb-4">
              5. Limitation of Liability
            </h2>
            <p>
              TheKnowledgeOrbits provides synthetic intelligence based on public
              data. We do not guarantee the 100% accuracy of AI-generated
              answers or current affairs summaries. Users should cross-verify
              all critical facts with official Government of India sources or
              original news outlets.
            </p>
          </section>
        </div>

        {/* Call to action */}
        <div className="mt-12 text-center">
          <Link href="/contact">
            <Button
              size="lg"
              className="rounded-full px-8 bg-blue-600 hover:bg-blue-700"
            >
              Contact the Developer
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
