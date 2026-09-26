/**
 * Universal footer — the site's primary navigation for everything the header
 * cannot hold, and the only entry point to About/Contact on mobile.
 *
 * Structure serves three audiences deliberately:
 *   Learn         — aspirants, the core user
 *   Resources     — self-serve reference material, useful to a layman too
 *   For educators — teachers and institutions, the future B2B side
 *   Company       — trust signals; AdSense and Search Console both look here
 *
 * `soon: true` marks a route that does not exist yet. The link still renders
 * and is still clickable, as requested, but is visibly labelled so a visitor is
 * not walked into a 404 and a crawler is not invited to index one. Flip the
 * flag to false as each page ships — nothing else needs to change.
 *
 * "Support the Code" sits inside the brand column, deliberately apart from the
 * legal navigation. These are voluntary developer tips for the open-source
 * work, not a product a student buys — conflating the two in one row would
 * misrepresent both to a visitor and to a payment aggregator's reviewer.
 */

"use client";

import React from "react";
import Link from "next/link";
import {
  BookOpen,
  Github,
  Twitter,
  Linkedin,
  Facebook,
  Mail,
  MapPin,
  Heart,
} from "lucide-react";

type FooterLink = { label: string; href: string; soon?: boolean };

const footerColumns: { heading: string; links: FooterLink[] }[] = [
  {
    heading: "Learn",
    links: [
      { label: "Daily Current Affairs", href: "/daily-ca" },
      { label: "Current Affairs Archive", href: "/current-affairs" },
      { label: "UPSC Syllabus", href: "/subjects" },
      { label: "Browse Topics", href: "/topics" },
      { label: "Knowledge Graph", href: "/knowledge" },
      { label: "Articles", href: "/articles" },
      { label: "Practice Quiz", href: "/assessment" },
      { label: "Research Agent", href: "/research_agent" },
    ],
  },
  {
    heading: "Resources",
    links: [
      { label: "UPSC Syllabus", href: "/resources/syllabus", soon: true },
      { label: "Previous Year Questions", href: "/resources/pyq", soon: true },
      { label: "Preparation Guide", href: "/resources/guide", soon: true },
      { label: "Study Timetable", href: "/resources/timetable", soon: true },
      { label: "Glossary", href: "/resources/glossary", soon: true },
      { label: "Blog", href: "/blog", soon: true },
    ],
  },
  {
    heading: "For educators",
    links: [
      { label: "For Teachers", href: "/educators", soon: true },
      { label: "Institutional Access", href: "/institutions", soon: true },
      { label: "Bulk Licensing", href: "/institutions/pricing", soon: true },
      { label: "Content Partnership", href: "/partners", soon: true },
      { label: "Educator Support", href: "/contact" },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "About Us", href: "/about" },
      { label: "Contact", href: "/contact" },
      { label: "Help Centre", href: "/help", soon: true },
      { label: "FAQs", href: "/faqs", soon: true },
      { label: "Careers", href: "/careers", soon: true },
      { label: "System Status", href: "/health" },
    ],
  },
];

const legalLinks: FooterLink[] = [
  { label: "Privacy Policy", href: "/privacy" },
  { label: "Terms of Service", href: "/terms" },
  { label: "Cookie Policy", href: "/cookies" },
  { label: "Accessibility", href: "/accessibility", soon: true },
];

const socialLinks = [
  { icon: Twitter, href: "#", label: "Twitter" },
  { icon: Github, href: "#", label: "GitHub" },
  { icon: Linkedin, href: "#", label: "LinkedIn" },
  { icon: Facebook, href: "#", label: "Facebook" },
];

/**
 * Public creator pages. Both open in a new tab so a supporter never loses
 * their place in the site, and both carry `rel="noopener noreferrer"` — the
 * destination must never get a handle on our window.
 */
const supportLinks: { label: string; href: string; note: string }[] = [
  {
    label: "Buy Me a Coffee",
    href: "https://buymeacoffee.com/vishalgoyal25",
    note: "Card payments, worldwide",
  },
  {
    label: "Ko-fi",
    href: "https://ko-fi.com/vishalgoyal25",
    note: "0% platform fee",
  },
];

function FooterLinkItem({ link }: { link: FooterLink }) {
  return (
    <Link
      href={link.href}
      className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-primary"
    >
      {link.label}
      {link.soon && (
        <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Soon
        </span>
      )}
    </Link>
  );
}

export default function Footer() {
  return (
    <footer className="border-t border-border bg-card pt-12 pb-8 sm:pt-16">
      <div className="container mx-auto px-4">
        <div className="mb-12 grid grid-cols-1 gap-10 lg:grid-cols-6 lg:gap-8">
          <div className="space-y-5 lg:col-span-2">
            <Link href="/" className="flex items-center space-x-2">
              <BookOpen className="h-7 w-7 text-primary" />
              <span className="text-xl font-semibold tracking-tight text-foreground">
                TheKnowledgeOrbits
              </span>
            </Link>
            <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
              Empowering UPSC aspirants with AI-driven insights, personalized
              learning modules, and the most comprehensive knowledge orbits
              available. Master the syllabus with intelligence.
            </p>
            <div className="flex space-x-3">
              {socialLinks.map((social) => (
                <Link
                  key={social.label}
                  href={social.href}
                  className="rounded-lg bg-muted/40 p-2 text-muted-foreground transition-all hover:bg-accent hover:text-primary"
                  aria-label={social.label}
                >
                  <social.icon className="h-4 w-4" />
                </Link>
              ))}
            </div>

            <section aria-labelledby="footer-support-heading" className="pt-1">
              <h3
                id="footer-support-heading"
                className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-foreground"
              >
                <Heart
                  className="h-4 w-4 fill-rose-500 text-rose-500"
                  aria-hidden="true"
                />
                Support the Code
              </h3>
              <p className="mb-3 max-w-sm text-xs leading-relaxed text-muted-foreground">
                This platform is open source and built solo. If it helped your
                preparation, you can buy the developer a coffee — entirely
                voluntary, and it unlocks nothing on the site.
              </p>
              <div className="flex flex-wrap gap-2">
                {supportLinks.map((support) => (
                  <a
                    key={support.label}
                    href={support.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={support.note}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-muted/40 px-3 py-1.5 text-xs font-medium text-muted-foreground transition-all hover:border-primary/40 hover:bg-accent hover:text-primary"
                  >
                    {support.label}
                  </a>
                ))}
              </div>
            </section>
          </div>

          <div className="grid grid-cols-2 gap-8 sm:grid-cols-4 lg:col-span-4">
            {footerColumns.map((column) => (
              <div key={column.heading}>
                <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-foreground">
                  {column.heading}
                </h3>
                <ul className="space-y-3">
                  {column.links.map((link) => (
                    <li key={link.label}>
                      <FooterLinkItem link={link} />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="border-t border-border pt-6">
          <nav
            aria-label="Legal"
            className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2"
          >
            {legalLinks.map((link) => (
              <FooterLinkItem key={link.label} link={link} />
            ))}
          </nav>

          <div className="flex flex-col items-start justify-between gap-4 md:flex-row md:items-center">
            <p className="text-sm text-muted-foreground">
              © {new Date().getFullYear()} TheKnowledgeOrbits. All rights
              reserved.
              <span className="mx-2 hidden md:inline">|</span>
              <span className="block md:inline">
                Made with care for UPSC aspirants.
              </span>
            </p>

            <div className="flex flex-col gap-2 text-xs text-muted-foreground sm:flex-row sm:items-center sm:gap-5">
              <a
                href="mailto:support@knowledgeorbits.com"
                className="flex items-center gap-2 transition-colors hover:text-primary"
              >
                <Mail className="h-3.5 w-3.5" />
                support@knowledgeorbits.com
              </a>
              <span className="flex items-center gap-2">
                <MapPin className="h-3.5 w-3.5" />
                New Delhi, India
              </span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
