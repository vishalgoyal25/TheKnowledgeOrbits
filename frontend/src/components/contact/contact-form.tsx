"use client";

/**
 * Contact form — extracted from app/contact/page.tsx during G2.
 *
 * The page had to be "use client" purely because of this form's state. Pulling
 * the form out lets the page become a server component and export `metadata`,
 * which G3 needs, while the interactive part stays exactly as interactive as
 * it was. Submit behaviour, payload and toasts are unchanged.
 */
import React, { useState } from "react";
import { Loader2, MessageSquare, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { supportAPI } from "@/lib/api/support";
import { ContentCard } from "@/components/shared/content-card";

const EMPTY_FORM = {
  name: "",
  email: "",
  phone: "",
  institution: "",
  message: "",
};

export function ContactForm() {
  const { toast } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState(EMPTY_FORM);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      await supportAPI.submitFeedback({
        ...formData,
        user_type: "other", // Use the feedback API we built
      });
      toast({
        title: "Message Sent!",
        description:
          "We've received your query and will get back to you shortly.",
      });
      setFormData(EMPTY_FORM);
    } catch {
      toast({
        title: "Error",
        description: "Failed to send message. Please try again later.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ContentCard className="p-6 sm:p-8">
      <div className="mb-6 flex items-center gap-3">
        <MessageSquare className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold tracking-tight text-foreground sm:text-xl">
          Send a Quick Message
        </h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <div className="space-y-2">
            <label
              htmlFor="contact-name"
              className="text-sm font-medium text-foreground"
            >
              Your Name *
            </label>
            <Input
              id="contact-name"
              placeholder="John Doe"
              value={formData.name}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
              required
            />
          </div>
          <div className="space-y-2">
            <label
              htmlFor="contact-email"
              className="text-sm font-medium text-foreground"
            >
              Email Address *
            </label>
            <Input
              id="contact-email"
              type="email"
              placeholder="john@example.com"
              value={formData.email}
              onChange={(e) =>
                setFormData({ ...formData, email: e.target.value })
              }
              required
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <div className="space-y-2">
            <label
              htmlFor="contact-phone"
              className="text-sm font-medium text-foreground"
            >
              Phone Number (Optional)
            </label>
            <Input
              id="contact-phone"
              placeholder="+91..."
              value={formData.phone}
              onChange={(e) =>
                setFormData({ ...formData, phone: e.target.value })
              }
            />
          </div>
          <div className="space-y-2">
            <label
              htmlFor="contact-institution"
              className="text-sm font-medium text-foreground"
            >
              Institution/Batch
            </label>
            <Input
              id="contact-institution"
              placeholder="e.g. DU, IGNOU, etc."
              value={formData.institution}
              onChange={(e) =>
                setFormData({ ...formData, institution: e.target.value })
              }
            />
          </div>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="contact-message"
            className="text-sm font-medium text-foreground"
          >
            How can we help? *
          </label>
          <Textarea
            id="contact-message"
            placeholder="Write your message here..."
            className="min-h-[160px] resize-none"
            value={formData.message}
            onChange={(e) =>
              setFormData({ ...formData, message: e.target.value })
            }
            required
          />
        </div>

        <Button
          type="submit"
          size="lg"
          className="w-full gap-2"
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Delivering Message...
            </>
          ) : (
            <>
              <Send className="h-4 w-4" />
              Send Message
            </>
          )}
        </Button>
      </form>
    </ContentCard>
  );
}
