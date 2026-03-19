import React from "react";
import { Cookie, Info, Lock, Zap, CheckCircle } from "lucide-react";
import Link from "next/link";

export default function CookiePolicy() {
  return (
    <div className="bg-slate-50 min-h-screen py-16">
      <div className="container mx-auto px-4 max-w-4xl">
        {/* Header */}
        <div className="bg-white rounded-3xl p-8 md:p-12 shadow-sm border border-slate-200 mb-8 relative overflow-hidden text-center md:text-left">
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <Cookie size={160} />
          </div>
          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 text-amber-600 text-xs font-bold uppercase tracking-wider mb-4">
              <Cookie className="h-3.5 w-3.5" /> Browser Interaction
            </div>
            <h1 className="text-4xl md:text-5xl font-black text-slate-900 mb-4 tracking-tight">
              Cookie Policy
            </h1>
            <p className="text-slate-500 font-medium text-lg max-w-2xl">
              We use only essential technical cookies to keep your study
              sessions smooth. No advertising or tracking cookies are used here.
            </p>
          </div>
        </div>

        {/* Hobby Project Awareness */}
        <div className="bg-amber-50 border-2 border-amber-100 rounded-2xl p-6 mb-10 flex flex-col md:flex-row gap-6 items-center">
          <div className="h-14 w-14 shrink-0 bg-amber-100 rounded-full flex items-center justify-center text-amber-600">
            <Info className="h-8 w-8 text-amber-600" />
          </div>
          <div>
            <h2 className="font-bold text-amber-900 uppercase text-xs tracking-widest mb-1">
              Transparency First
            </h2>
            <p className="text-amber-800 text-xs leading-relaxed">
              As a hobby and educational project, we don&apos;t use complex
              tracking pixels or third-party advertising cookies. We only use
              browser-side storage that is strictly necessary for our platform
              to function.
            </p>
          </div>
        </div>

        {/* Content */}
        <div className="bg-white rounded-3xl p-8 md:p-12 shadow-sm border border-slate-200 space-y-12 text-slate-700 leading-relaxed">
          {/* Section 1 */}
          <section>
            <div className="flex items-center gap-3 mb-6">
              <h2 className="text-2xl font-black text-slate-900">
                What are Cookies?
              </h2>
            </div>
            <p className="mb-4">
              Cookies are small text files that your browser stores on your
              computer. They are useful because they allow our website to
              recognize you (for example, so you don&apos;t have to log in every
              time you open a new tab).
            </p>
          </section>

          {/* Section 2 */}
          <section>
            <div className="flex items-center gap-3 mb-6">
              <h2 className="text-2xl font-black text-slate-900">
                Types of Cookies We Use
              </h2>
            </div>
            <div className="space-y-6">
              {/* Essential Cookies */}
              <div className="p-6 bg-slate-50 rounded-2xl border border-slate-100 flex flex-col md:flex-row gap-6">
                <div className="h-10 w-10 shrink-0 bg-blue-100 text-blue-600 rounded-xl flex items-center justify-center">
                  <Lock className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-900 mb-1">
                    Strictly Necessary Cookies (Auth)
                  </h3>
                  <p className="text-sm text-slate-500 mb-3 underline italic uppercase tracking-widest text-[10px]">
                    ALWAYS ENABLED
                  </p>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    We use these cookies to manage your login session (via
                    Supabase/JWT). Without these, our dashboard and preparation
                    tracking features won&apos;t work.
                  </p>
                </div>
              </div>

              {/* Preference Cookies */}
              <div className="p-6 bg-slate-50 rounded-2xl border border-slate-100 flex flex-col md:flex-row gap-6">
                <div className="h-10 w-10 shrink-0 bg-purple-100 text-purple-600 rounded-xl flex items-center justify-center">
                  <Zap className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-900 mb-1">
                    Functionality Cookies (Study State)
                  </h3>
                  <p className="text-sm text-slate-500 mb-3 underline italic uppercase tracking-widest text-[10px]">
                    OPTIONAL
                  </p>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    These remember preferences like your theme choice
                    (Light/Dark mode) or which filter you used last on the
                    Current Affairs page.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Section 3 */}
          <section>
            <div className="flex items-center gap-3 mb-6">
              <h2 className="text-2xl font-black text-slate-900">
                Third-Party Cookies
              </h2>
            </div>
            <div className="bg-red-50 border-l-4 border-red-500 p-6 rounded-r-2xl">
              <p className="text-red-900 text-sm leading-relaxed italic mb-4">
                We currently use{" "}
                <strong>
                  ZERO third-party advertising or marketing cookies
                </strong>
                . We are not interested in tracking you across the web.
              </p>
              <div className="flex items-center gap-2 text-red-700 font-bold text-xs uppercase tracking-widest">
                <CheckCircle className="h-4 w-4" /> 100% Privacy-First Stack
              </div>
            </div>
          </section>

          {/* How to Control Cookies */}
          <section>
            <h2 className="text-2xl font-black text-slate-900 mb-4">
              How to Control Cookies
            </h2>
            <p className="mb-4">
              You can control and delete cookies through your browser settings.
              Most browsers allow you to block all cookies, but please note that
              if you block all cookies, many parts of this project (like logging
              in) will break.
            </p>
          </section>

          {/* Contact Developer */}
          <section className="text-center pt-8 border-t border-slate-100">
            <Link
              href="/terms"
              className="text-blue-600 font-bold hover:underline"
            >
              Learn more in our Terms of Service
            </Link>
          </section>
        </div>

        {/* Footer */}
        <div className="mt-12 text-center text-sm font-bold text-slate-400 uppercase tracking-widest">
          <Link href="/" className="hover:text-blue-500 transition-colors">
            Return Home
          </Link>
        </div>
      </div>
    </div>
  );
}
