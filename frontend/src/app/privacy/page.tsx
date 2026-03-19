import React from "react";
import { ShieldCheck, Lock, Eye, Mail, Database } from "lucide-react";
import Link from "next/link";

export default function PrivacyPolicy() {
  return (
    <div className="bg-slate-50 min-h-screen py-16">
      <div className="container mx-auto px-4 max-w-4xl">
        {/* Header */}
        <div className="bg-white rounded-3xl p-8 md:p-12 shadow-sm border border-slate-200 mb-8 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <Lock size={160} />
          </div>
          <div className="relative z-10 text-center md:text-left">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 text-emerald-600 text-xs font-bold uppercase tracking-wider mb-4">
              <ShieldCheck className="h-3.5 w-3.5" /> User Data Shield
            </div>
            <h1 className="text-4xl md:text-5xl font-black text-slate-900 mb-4 tracking-tight">
              Privacy Policy
            </h1>
            <p className="text-slate-500 font-medium text-lg max-w-2xl">
              We respect your privacy as a fellow learner. Here is exactly how
              your data is handled in this hobby project.
            </p>
          </div>
        </div>

        {/* Hobby Project Notice */}
        <div className="bg-emerald-50 border-2 border-emerald-100 rounded-2xl p-6 mb-10">
          <p className="text-emerald-800 text-sm leading-relaxed text-center">
            <strong>TheKnowledgeOrbits</strong> is a non-commercial educational
            project. <strong>We do not sell, rent, or trade user data.</strong>{" "}
            Our primary interest is in the technical implementation of
            personalized learning.
          </p>
        </div>

        {/* Content */}
        <div className="bg-white rounded-3xl p-8 md:p-12 shadow-sm border border-slate-200 space-y-12 text-slate-700 leading-relaxed">
          {/* Section 1 */}
          <section>
            <div className="flex items-center gap-3 mb-4">
              <div className="h-10 w-10 bg-emerald-100 text-emerald-600 rounded-xl flex items-center justify-center">
                <Database className="h-5 w-5" />
              </div>
              <h2 className="text-2xl font-black text-slate-900">
                What Data We Collect
              </h2>
            </div>
            <ul className="list-disc pl-6 space-y-3">
              <li>
                <strong>Account Information:</strong> We store your name and
                email when you register to allow you to log back in and save
                your progress.
              </li>
              <li>
                <strong>Study Analytics:</strong> We track which quizzes you
                take and which articles you read to calculate your "Topic
                Mastery" scores and progress.
              </li>
              <li>
                <strong>Technical Logs:</strong> Like most sites, we log basic
                technical details (browser type, timestamp) to help us debug the
                server (especially during our production-hardening phase).
              </li>
            </ul>
          </section>

          {/* Section 2 */}
          <section>
            <div className="flex items-center gap-3 mb-4">
              <div className="h-10 w-10 bg-blue-100 text-blue-600 rounded-xl flex items-center justify-center">
                <Eye className="h-5 w-5" />
              </div>
              <h2 className="text-2xl font-black text-slate-900">
                How We Use Your Data
              </h2>
            </div>
            <p className="mb-4">
              Your data is strictly used for one purpose:{" "}
              <strong>Enhancing your preparation experience.</strong>
            </p>
            <ul className="list-disc pl-6 space-y-3">
              <li>
                To provide you with a "Dashboard" that shows your personal
                preparation history.
              </li>
              <li>
                To allow you to "Bookmark" articles for offline or future
                reading.
              </li>
              <li>
                To optimize our AI recommendation engine to suggest topics you
                need to focus on.
              </li>
            </ul>
          </section>

          {/* Section 4 */}
          <section>
            <div className="flex items-center gap-3 mb-4">
              <div className="h-10 w-10 bg-amber-100 text-amber-600 rounded-xl flex items-center justify-center">
                <Mail className="h-5 w-5" />
              </div>
              <h2 className="text-2xl font-black text-slate-900">
                Your Rights
              </h2>
            </div>
            <p className="mb-4 font-bold italic text-slate-900">
              You are the master of your data.
            </p>
            <p className="mb-6">
              Since this is a student project, we strictly follow the principles
              of <strong>Data Minimization</strong>. You can:
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                <h3 className="font-bold text-slate-800 mb-1 uppercase text-[10px] tracking-widest">
                  Delete Information
                </h3>
                <p className="text-xs text-slate-500">
                  Email us anytime to request permanent deletion of your
                  account/data.
                </p>
              </div>
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                <h3 className="font-bold text-slate-800 mb-1 uppercase text-[10px] tracking-widest">
                  Access Information
                </h3>
                <p className="text-xs text-slate-500">
                  Contact us if you want a copy of your study history stored in
                  our DB.
                </p>
              </div>
            </div>
          </section>

          {/* Section 5 */}
          <section>
            <div className="flex items-center gap-3 mb-4">
              <div className="h-10 w-10 bg-indigo-100 text-indigo-600 rounded-xl flex items-center justify-center">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <h2 className="text-2xl font-black text-slate-900">Contact Us</h2>
            </div>
            <p className="mb-4">
              If you have any questions about this hobby project&apos;s privacy
              practices, feel free to reach out to the developer:
            </p>
            <div className="bg-slate-50 p-4 rounded-xl font-mono text-sm border border-slate-100 flex items-center gap-2">
              <Mail className="h-4 w-4 text-emerald-500" />{" "}
              support@knowledgeorbits.com
            </div>
          </section>
        </div>

        {/* Back link */}
        <div className="mt-12 text-center text-sm font-bold text-slate-400 uppercase tracking-widest">
          <Link href="/" className="hover:text-blue-500 transition-colors">
            Return Home
          </Link>
        </div>
      </div>
    </div>
  );
}
