import React from "react";
import {
  ShieldCheck,
  Lock,
  Eye,
  Mail,
  Database,
  BarChart3,
  Clock,
  Globe,
  Scale,
} from "lucide-react";
import Link from "next/link";

import { buildMetadata } from "@/lib/seo/metadata";

/**
 * /privacy — G3.7 (FEATURES_GROWTH_STACK.md §7.8).
 *
 * Every statement here describes something the code actually does:
 *   - GA4 page views (components/telemetry/GoogleAnalytics.tsx, PageViewTracker)
 *   - first-party VisitLog / ContentRead (engines/telemetry) with hashed IPs and
 *     30-day / 365-day retention (prune_telemetry, chained on the daily cron)
 *   - auth cookies access_token / refresh_token (lib/auth/token-manager.ts)
 *   - the processors the stack runs on (Vercel, Render, Supabase, Cloudinary,
 *     Google Analytics, Sentry, Brevo, Telegram)
 * When any of those changes, this page changes in the same PR.
 */

export const metadata = buildMetadata({
  title: "Privacy Policy",
  description:
    "How TheKnowledgeOrbits collects, uses and protects your data — analytics, cookies, retention and your rights under the DPDP Act.",
  path: "/privacy",
});

const LAST_UPDATED = "16 September 2026";

function SectionHeading({
  icon: Icon,
  tone,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  tone: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <div
        className={`h-10 w-10 ${tone} rounded-xl flex items-center justify-center`}
      >
        <Icon className="h-5 w-5" />
      </div>
      <h2 className="text-2xl font-semibold text-foreground">{children}</h2>
    </div>
  );
}

export default function PrivacyPolicy() {
  return (
    <div className="bg-muted/40 min-h-screen py-16">
      <div className="container mx-auto px-4 max-w-4xl">
        {/* Header */}
        <div className="bg-card rounded-lg p-8 md:p-12 shadow-sm border border-border mb-8 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <Lock size={160} />
          </div>
          <div className="relative z-10 text-center md:text-left">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 text-emerald-600 text-xs font-bold uppercase tracking-wider mb-4">
              <ShieldCheck className="h-3.5 w-3.5" /> Privacy
            </div>
            <h1 className="text-4xl md:text-5xl font-semibold text-foreground mb-4 tracking-tight">
              Privacy Policy
            </h1>
            <p className="text-muted-foreground font-medium text-lg max-w-2xl">
              What we collect, why, for how long, who processes it, and the
              rights you have over it. Written to match what the code does.
            </p>
            <p className="mt-4 text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Last updated {LAST_UPDATED}
            </p>
          </div>
        </div>

        {/* Summary */}
        <div className="bg-emerald-50 border-2 border-emerald-100 rounded-lg p-6 mb-10">
          <p className="text-emerald-800 text-sm leading-relaxed text-center">
            <strong>TheKnowledgeOrbits</strong> is a non-commercial educational
            project run by a single developer in India.{" "}
            <strong>We do not sell, rent or trade personal data</strong>, we do
            not show advertising, and every visitor-level record we keep is
            either aggregated or pseudonymised. You can read the whole site
            without an account.
          </p>
        </div>

        <div className="bg-card rounded-lg p-8 md:p-12 shadow-sm border border-border space-y-12 text-foreground leading-relaxed">
          {/* 1. Who */}
          <section>
            <SectionHeading icon={Globe} tone="bg-slate-100 text-slate-700">
              Who is responsible
            </SectionHeading>
            <p>
              The site is operated by its developer as the{" "}
              <strong>data fiduciary</strong> in the sense of India&apos;s
              Digital Personal Data Protection Act, 2023 (the &ldquo;DPDP
              Act&rdquo;). Questions and requests go to the address in the last
              section. This policy applies to{" "}
              <strong>theknowledgeorbits.com</strong> and to the Telegram bot
              operated under the same name.
            </p>
          </section>

          {/* 2. What we collect */}
          <section>
            <SectionHeading
              icon={Database}
              tone="bg-emerald-100 text-emerald-600"
            >
              What we collect
            </SectionHeading>
            <ul className="list-disc pl-6 space-y-3">
              <li>
                <strong>If you create an account:</strong> your name, email
                address and a password. The password is stored only as an Argon2
                hash — we cannot read it. Login is by short-lived tokens (see
                Cookies below).
              </li>
              <li>
                <strong>If you use the site logged in:</strong> the quizzes you
                attempt and your answers, the articles you bookmark, the
                articles you generate into your private notebook, and which
                articles you have read. This is what your dashboard and
                &ldquo;topic mastery&rdquo; are computed from.
              </li>
              <li>
                <strong>If you ask the AI Research Agent a question:</strong>{" "}
                the question, the generated report and its sources are stored as
                a research session so you can reopen it. Anonymous use is
                rate-limited by a salted hash of your IP address, never the
                address itself.
              </li>
              <li>
                <strong>If you use the Telegram bot:</strong> your Telegram chat
                identifier is stored so we can reply to you. Everything that
                leaves our database for monitoring carries a salted hash of it,
                never the identifier.
              </li>
              <li>
                <strong>
                  Every visitor, with or without an account — see the next
                  section.
                </strong>
              </li>
            </ul>
          </section>

          {/* 3. Analytics */}
          <section>
            <SectionHeading icon={BarChart3} tone="bg-blue-100 text-blue-600">
              Analytics — what a page view records
            </SectionHeading>
            <p className="mb-4">
              We measure how the site is used with two independent mechanisms.
              Neither is used to build a profile of you or to show you anything
              different.
            </p>
            <div className="space-y-4">
              <div className="p-5 bg-muted/40 rounded-xl border border-border">
                <h3 className="font-bold text-foreground mb-2">
                  Google Analytics 4 (third party)
                </h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Google&apos;s script records the pages you view, the page
                  title, your rough location (derived by Google from your IP),
                  device and browser type, and how you arrived. Google sets the
                  cookies <code>_ga</code> and <code>_ga_*</code> for this (see
                  the{" "}
                  <Link href="/cookies" className="text-blue-600 underline">
                    Cookie Policy
                  </Link>
                  ). Google processes this data under its own terms; we see only
                  aggregated reports. You can opt out with Google&apos;s{" "}
                  <a
                    href="https://tools.google.com/dlpage/gaoptout"
                    className="text-blue-600 underline"
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    browser add-on
                  </a>{" "}
                  or by blocking the cookies.
                </p>
              </div>
              <div className="p-5 bg-muted/40 rounded-xl border border-border">
                <h3 className="font-bold text-foreground mb-2">
                  Our own visit log (first party)
                </h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Our server records, for each page request: the path, the time,
                  the referring page, the browser&apos;s user-agent string, and
                  a <strong>one-way salted hash of your IP address</strong>. The
                  address itself is never written to disk. A second record notes
                  which article a browser finished reading, once per article per
                  day. Logged-in reads are linked to your account so your
                  progress can be shown to you; anonymous reads are linked to
                  the hash only.
                </p>
              </div>
            </div>
          </section>

          {/* 4. Use */}
          <section>
            <SectionHeading icon={Eye} tone="bg-indigo-100 text-indigo-600">
              How we use it
            </SectionHeading>
            <ul className="list-disc pl-6 space-y-3">
              <li>
                To run the service: log you in, keep your notebook, bookmarks
                and quiz history, and reply to your research questions.
              </li>
              <li>
                To understand which subjects and articles are read, so the daily
                content pipeline generates what is useful.
              </li>
              <li>
                To keep the service up: detect abuse, rate-limit anonymous use,
                debug errors.
              </li>
              <li>
                <strong>Not</strong> for advertising, profiling, selling, or any
                purpose beyond running and improving this site.
              </li>
            </ul>
          </section>

          {/* 5. Retention */}
          <section>
            <SectionHeading icon={Clock} tone="bg-amber-100 text-amber-600">
              How long we keep it
            </SectionHeading>
            <ul className="list-disc pl-6 space-y-3">
              <li>
                <strong>Visit log:</strong> 30 days, then deleted automatically
                every night.
              </li>
              <li>
                <strong>Article-read records:</strong> 365 days, then deleted
                automatically.
              </li>
              <li>
                <strong>
                  Account, notebook, bookmarks, quiz history, research sessions:
                </strong>{" "}
                until you delete your account or ask us to.
              </li>
              <li>
                <strong>Server error reports (Sentry):</strong> for the
                retention period of our Sentry plan — at most 90 days.
              </li>
              <li>
                <strong>Google Analytics:</strong> user-level event data for the
                period set on the Analytics property, between 2 and 14 months;
                aggregated reports are kept by Google indefinitely.
              </li>
            </ul>
          </section>

          {/* 6. Processors */}
          <section>
            <SectionHeading icon={Globe} tone="bg-cyan-100 text-cyan-700">
              Who processes it on our behalf
            </SectionHeading>
            <p className="mb-4">
              We run on hosted services. Each receives only what its job
              requires:
            </p>
            <ul className="list-disc pl-6 space-y-2 text-sm">
              <li>
                <strong>Vercel</strong> — serves the website (page requests pass
                through it).
              </li>
              <li>
                <strong>Render</strong> — runs our backend and scheduled jobs.
              </li>
              <li>
                <strong>Supabase</strong> — hosts the database where the data
                above is stored.
              </li>
              <li>
                <strong>Cloudinary</strong> — stores and serves article images.
              </li>
              <li>
                <strong>Google Analytics</strong> — usage statistics, as above.
              </li>
              <li>
                <strong>Sentry</strong> — receives error reports when something
                breaks; may include the URL and browser details of the request
                that failed.
              </li>
              <li>
                <strong>Brevo</strong> — sends account emails (verification,
                password reset).
              </li>
              <li>
                <strong>Telegram</strong> — carries bot messages if you use the
                bot.
              </li>
              <li>
                <strong>AI providers (Groq, Mistral, OpenRouter)</strong> —
                receive the text of research questions and article prompts to
                generate answers. They do not receive your name, email or
                account identifiers.
              </li>
            </ul>
            <p className="mt-4 text-sm text-muted-foreground">
              Some of these providers operate outside India. We rely on their
              standard contractual terms for such transfers.
            </p>
          </section>

          {/* 7. Rights */}
          <section>
            <SectionHeading icon={Scale} tone="bg-rose-100 text-rose-600">
              Your rights
            </SectionHeading>
            <p className="mb-6">
              Under the DPDP Act you can ask us, at any time and free of charge,
              to:
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[
                [
                  "Access",
                  "receive a summary of the personal data we hold about you and how it is used.",
                ],
                [
                  "Correct",
                  "fix inaccurate or incomplete data — your name and email you can change yourself in Settings.",
                ],
                [
                  "Erase",
                  "delete your account and everything linked to it. Visit-log hashes cannot be linked back to you and expire on their own within 30 days.",
                ],
                [
                  "Withdraw consent",
                  "stop analytics for your browser by blocking the Google cookies; stop all account processing by deleting the account.",
                ],
                ["Nominate", "name a person to exercise these rights for you."],
                [
                  "Complain",
                  "raise a grievance with us first (we answer within 30 days), and thereafter with the Data Protection Board of India.",
                ],
              ].map(([title, body]) => (
                <div
                  key={title}
                  className="p-4 bg-muted/40 rounded-xl border border-border"
                >
                  <h3 className="font-bold text-foreground mb-1 uppercase text-[10px] tracking-widest">
                    {title}
                  </h3>
                  <p className="text-xs text-muted-foreground">{body}</p>
                </div>
              ))}
            </div>
          </section>

          {/* 8. Children, ads, changes */}
          <section>
            <SectionHeading
              icon={ShieldCheck}
              tone="bg-violet-100 text-violet-600"
            >
              Children, advertising, changes
            </SectionHeading>
            <ul className="list-disc pl-6 space-y-3">
              <li>
                The site is for adults preparing for the UPSC Civil Services
                examination. We do not knowingly collect data from anyone under
                18; if you believe a child has created an account, contact us
                and it will be removed.
              </li>
              <li>
                <strong>We currently show no advertising</strong> and set no
                advertising cookies. If that ever changes, this page and the
                Cookie Policy will be updated <em>before</em> any ad script is
                loaded, and you will be asked for consent where the law requires
                it.
              </li>
              <li>
                Material changes to this policy are announced by updating the
                date at the top. Continued use after a change means you accept
                the updated policy.
              </li>
            </ul>
          </section>

          {/* 9. Contact */}
          <section>
            <SectionHeading icon={Mail} tone="bg-indigo-100 text-indigo-600">
              Contact
            </SectionHeading>
            <p className="mb-4">
              For any request under this policy — access, correction, deletion,
              a question — write to:
            </p>
            <div className="bg-muted/40 p-4 rounded-xl font-mono text-sm border border-border flex items-center gap-2">
              <Mail className="h-4 w-4 text-emerald-500" />{" "}
              support@knowledgeorbits.com
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              Please write from the email address on your account so we can
              verify the request. We reply within 30 days.
            </p>
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
