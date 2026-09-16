import React from "react";
import { Cookie, Info, Lock, Zap, CheckCircle } from "lucide-react";
import Link from "next/link";

import { buildMetadata } from "@/lib/seo/metadata";

export const metadata = buildMetadata({
  title: "Cookie Policy",
  description:
    "Which cookies TheKnowledgeOrbits sets, what each is for, and how to control them.",
  path: "/cookies",
});

export default function CookiePolicy() {
  return (
    <div className="bg-muted/40 min-h-screen py-16">
      <div className="container mx-auto px-4 max-w-4xl">
        {/* Header */}
        <div className="bg-card rounded-lg p-8 md:p-12 shadow-sm border border-border mb-8 relative overflow-hidden text-center md:text-left">
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <Cookie size={160} />
          </div>
          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 text-amber-600 text-xs font-bold uppercase tracking-wider mb-4">
              <Cookie className="h-3.5 w-3.5" /> Browser Interaction
            </div>
            <h1 className="text-4xl md:text-5xl font-semibold text-foreground mb-4 tracking-tight">
              Cookie Policy
            </h1>
            <p className="text-muted-foreground font-medium text-lg max-w-2xl">
              Two first-party cookies keep you logged in, and Google Analytics
              sets two more to count page views. No advertising cookies.
            </p>
          </div>
        </div>

        {/* Hobby Project Awareness */}
        <div className="bg-amber-50 border-2 border-amber-100 rounded-lg p-6 mb-10 flex flex-col md:flex-row gap-6 items-center">
          <div className="h-14 w-14 shrink-0 bg-amber-100 rounded-full flex items-center justify-center text-amber-600">
            <Info className="h-8 w-8 text-amber-600" />
          </div>
          <div>
            <h2 className="font-bold text-amber-900 uppercase text-xs tracking-widest mb-1">
              Transparency First
            </h2>
            <p className="text-amber-800 text-xs leading-relaxed">
              Exactly four cookies, listed below by name. Two are ours and
              strictly necessary (login); two are Google Analytics&apos; (usage
              statistics), which you can block without losing any feature. No
              advertising or cross-site tracking cookies. Updated 16 September
              2026.
            </p>
          </div>
        </div>

        {/* Content */}
        <div className="bg-card rounded-lg p-8 md:p-12 shadow-sm border border-border space-y-12 text-foreground leading-relaxed">
          {/* Section 1 */}
          <section>
            <div className="flex items-center gap-3 mb-6">
              <h2 className="text-2xl font-semibold text-foreground">
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
              <h2 className="text-2xl font-semibold text-foreground">
                Types of Cookies We Use
              </h2>
            </div>
            <div className="space-y-6">
              {/* Essential Cookies */}
              <div className="p-6 bg-muted/40 rounded-lg border border-border flex flex-col md:flex-row gap-6">
                <div className="h-10 w-10 shrink-0 bg-blue-100 text-blue-600 rounded-xl flex items-center justify-center">
                  <Lock className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-foreground mb-1">
                    Strictly Necessary Cookies (Auth)
                  </h3>
                  <p className="text-sm text-muted-foreground mb-3 underline italic uppercase tracking-widest text-[10px]">
                    ALWAYS ENABLED
                  </p>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    <code>access_token</code> and <code>refresh_token</code> —
                    set only when you log in, first-party,{" "}
                    <code>SameSite=Lax</code>, expiring after 7 days. They carry
                    your login session to our backend. Without them the
                    dashboard, notebook and bookmarks cannot work. Logging out
                    deletes them.
                  </p>
                </div>
              </div>

              {/* Analytics Cookies */}
              <div className="p-6 bg-muted/40 rounded-lg border border-border flex flex-col md:flex-row gap-6">
                <div className="h-10 w-10 shrink-0 bg-purple-100 text-purple-600 rounded-xl flex items-center justify-center">
                  <Zap className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-foreground mb-1">
                    Analytics Cookies (Google Analytics 4)
                  </h3>
                  <p className="text-sm text-muted-foreground mb-3 underline italic uppercase tracking-widest text-[10px]">
                    THIRD PARTY · BLOCKABLE
                  </p>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    <code>_ga</code> and <code>_ga_*</code> — set by Google
                    Analytics to tell one visitor&apos;s page views from
                    another&apos;s, for up to 2 years. They give us aggregated
                    statistics (which pages are read, from which regions) and
                    nothing about you individually. Blocking them removes no
                    feature. Details and opt-out in the{" "}
                    <Link href="/privacy" className="text-blue-600 underline">
                      Privacy Policy
                    </Link>
                    .
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Section 3 */}
          <section>
            <div className="flex items-center gap-3 mb-6">
              <h2 className="text-2xl font-semibold text-foreground">
                Advertising and Tracking Cookies
              </h2>
            </div>
            <div className="bg-red-50 border-l-4 border-red-500 p-6 rounded-r-2xl">
              <p className="text-red-900 text-sm leading-relaxed italic mb-4">
                <strong>None.</strong> No advertising network, no social pixel,
                no cross-site tracker. Interface preferences (the knowledge-map
                view, the sidebar state) are kept in your browser&apos;s local
                storage, not in a cookie, and never leave your device. If
                advertising is ever introduced, this page changes first and
                consent is asked where the law requires it.
              </p>
              <div className="flex items-center gap-2 text-red-700 font-bold text-xs uppercase tracking-widest">
                <CheckCircle className="h-4 w-4" /> Four cookies, all named
                above
              </div>
            </div>
          </section>

          {/* How to Control Cookies */}
          <section>
            <h2 className="text-2xl font-semibold text-foreground mb-4">
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
          <section className="text-center pt-8 border-t border-border">
            <Link
              href="/terms"
              className="text-blue-600 font-bold hover:underline"
            >
              Learn more in our Terms of Service
            </Link>
          </section>
        </div>

        {/* Footer */}
        <div className="mt-12 text-center text-sm font-bold text-muted-foreground uppercase tracking-widest">
          <Link href="/" className="hover:text-blue-500 transition-colors">
            Return Home
          </Link>
        </div>
      </div>
    </div>
  );
}
