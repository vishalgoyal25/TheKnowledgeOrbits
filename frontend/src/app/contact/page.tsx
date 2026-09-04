/**
 * Contact — server component (G2).
 *
 * The form's state was the only reason this file carried "use client". That
 * moved to components/contact/contact-form.tsx, so the page can now export
 * `metadata` for G3 while the form stays exactly as interactive as before.
 *
 * Content is unchanged word for word.
 */
import type { Metadata } from "next";
import {
  Github,
  Globe,
  Linkedin,
  Mail,
  MapPin,
  Sparkles,
  Twitter,
} from "lucide-react";

import { PageHero } from "@/components/shared/page-hero";
import { Section } from "@/components/shared/section";
import { ContentCard } from "@/components/shared/content-card";
import { ContactForm } from "@/components/contact/contact-form";

export const metadata: Metadata = {
  title: "Contact | TheKnowledgeOrbits",
  description:
    "Have a question about our AI technology or looking for institutional access? We'd love to hear from you.",
};

const SOCIALS = [
  { label: "Twitter", href: "#", icon: Twitter },
  { label: "GitHub", href: "#", icon: Github },
  { label: "LinkedIn", href: "#", icon: Linkedin },
];

export default function ContactPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <PageHero
        eyebrow="Contact our team"
        title={
          <>
            Let&apos;s orbit <span className="text-primary">together</span>
          </>
        }
        description="Have a question about our AI technology or looking for institutional access? We'd love to hear from you."
      />

      <Section>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-4">
            <ContentCard tone="muted">
              <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10">
                <Mail className="h-5 w-5 text-primary" />
              </span>
              <h3 className="text-base font-semibold text-foreground">
                Email Us
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                support@knowledgeorbits.com
              </p>
            </ContentCard>

            <ContentCard tone="muted">
              <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10">
                <MapPin className="h-5 w-5 text-primary" />
              </span>
              <h3 className="text-base font-semibold text-foreground">
                Visit Us
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Digital First Platform, <br />
                New Delhi, India
              </p>
            </ContentCard>

            <ContentCard>
              <h3 className="text-base font-semibold text-foreground">
                Connect on Social
              </h3>
              <div className="mt-4 flex gap-3">
                {SOCIALS.map((social) => (
                  <a
                    key={social.label}
                    href={social.href}
                    aria-label={social.label}
                    className="flex h-11 w-11 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
                  >
                    <social.icon className="h-5 w-5" />
                  </a>
                ))}
              </div>
              <div className="mt-5 flex items-center gap-2 border-t border-border pt-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <Sparkles className="h-4 w-4 text-highlight" />
                Live Support Coming Soon
              </div>
            </ContentCard>
          </div>

          <div className="lg:col-span-2">
            <ContactForm />
          </div>
        </div>
      </Section>

      <Section tone="muted" className="border-t border-border">
        <div className="mx-auto max-w-lg text-center">
          <Globe className="mx-auto mb-4 h-10 w-10 text-muted-foreground" />
          <h2 className="text-xl font-semibold tracking-tight text-foreground">
            A Global Community of Learners
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
            Our servers are distributed across the globe to ensure your orbits
            load instantly, no matter where you are.
          </p>
        </div>
      </Section>
    </div>
  );
}
