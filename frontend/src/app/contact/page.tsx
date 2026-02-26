"use client";

import React, { useState } from "react";
import {
  Mail,
  MapPin,
  Send,
  MessageSquare,
  Twitter,
  Github,
  Linkedin,
  Loader2,
  Globe,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { supportAPI } from "@/lib/api/support";

export default function ContactPage() {
  const { toast } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    institution: "",
    message: "",
  });

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
      setFormData({
        name: "",
        email: "",
        phone: "",
        institution: "",
        message: "",
      });
    } catch (error) {
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
    <div className="flex flex-col min-h-screen bg-white">
      {/* 1. TOP HEADER SECTION */}
      <section className="pt-24 pb-16 bg-gradient-to-b from-slate-50 to-white border-b">
        <div className="container mx-auto px-4 text-center">
          <Badge className="mb-6 px-4 py-1.5 bg-blue-100 text-blue-600 border-blue-200">
            CONTACT OUR TEAM
          </Badge>
          <h1 className="text-4xl md:text-6xl font-black text-slate-900 tracking-tight mb-6">
            Let's Orbit{" "}
            <span className="text-blue-600 font-serif">Together</span>
          </h1>
          <p className="text-xl text-slate-600 max-w-2xl mx-auto leading-relaxed font-medium">
            Have a question about our AI technology or looking for institutional
            access? We'd love to hear from you.
          </p>
        </div>
      </section>

      {/* 2. CONTACT GRID */}
      <section className="py-24">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
            {/* Contact Info Cards */}
            <div className="space-y-6">
              <div className="p-8 rounded-3xl bg-blue-50 border border-blue-100 space-y-4">
                <div className="h-12 w-12 bg-blue-600 rounded-2xl flex items-center justify-center">
                  <Mail className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-900">Email Us</h3>
                  <p className="text-slate-600 font-medium">
                    support@knowledgeorbits.com
                  </p>
                </div>
              </div>

              <div className="p-8 rounded-3xl bg-emerald-50 border border-emerald-100 space-y-4">
                <div className="h-12 w-12 bg-emerald-600 rounded-2xl flex items-center justify-center">
                  <MapPin className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-900">Visit Us</h3>
                  <p className="text-slate-600 font-medium">
                    Digital First Platform, <br />
                    New Delhi, India
                  </p>
                </div>
              </div>

              <div className="p-8 rounded-3xl bg-slate-900 text-white space-y-6">
                <h3 className="text-xl font-bold">Connect on Social</h3>
                <div className="flex gap-4">
                  <a
                    href="#"
                    className="h-10 w-10 bg-white/10 rounded-xl flex items-center justify-center hover:bg-blue-600 transition-colors"
                  >
                    <Twitter className="h-5 w-5" />
                  </a>
                  <a
                    href="#"
                    className="h-10 w-10 bg-white/10 rounded-xl flex items-center justify-center hover:bg-slate-700 transition-colors"
                  >
                    <Github className="h-5 w-5" />
                  </a>
                  <a
                    href="#"
                    className="h-10 w-10 bg-white/10 rounded-xl flex items-center justify-center hover:bg-blue-700 transition-colors"
                  >
                    <Linkedin className="h-5 w-5" />
                  </a>
                </div>
                <div className="pt-4 flex items-center gap-2 text-slate-400 text-sm font-bold uppercase tracking-widest">
                  <Sparkles className="h-4 w-4 text-blue-400" />
                  Live Support Coming Soon
                </div>
              </div>
            </div>

            {/* Contact Form */}
            <div className="lg:col-span-2 p-10 rounded-3xl border border-slate-100 bg-white shadow-2xl shadow-slate-100">
              <div className="flex items-center gap-3 mb-8">
                <MessageSquare className="h-6 w-6 text-blue-600" />
                <h2 className="text-3xl font-black text-slate-900">
                  Send a Quick Message
                </h2>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700 ml-1">
                      Your Name *
                    </label>
                    <Input
                      placeholder="John Doe"
                      className="h-12 rounded-xl bg-slate-50 border-slate-100"
                      value={formData.name}
                      onChange={(e) =>
                        setFormData({ ...formData, name: e.target.value })
                      }
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700 ml-1">
                      Email Address *
                    </label>
                    <Input
                      type="email"
                      placeholder="john@example.com"
                      className="h-12 rounded-xl bg-slate-50 border-slate-100"
                      value={formData.email}
                      onChange={(e) =>
                        setFormData({ ...formData, email: e.target.value })
                      }
                      required
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700 ml-1">
                      Phone Number (Optional)
                    </label>
                    <Input
                      placeholder="+91..."
                      className="h-12 rounded-xl bg-slate-50 border-slate-100"
                      value={formData.phone}
                      onChange={(e) =>
                        setFormData({ ...formData, phone: e.target.value })
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700 ml-1">
                      Institution/Batch
                    </label>
                    <Input
                      placeholder="e.g. DU, IGNOU, etc."
                      className="h-12 rounded-xl bg-slate-50 border-slate-100"
                      value={formData.institution}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          institution: e.target.value,
                        })
                      }
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-bold text-slate-700 ml-1">
                    How can we help? *
                  </label>
                  <Textarea
                    placeholder="Write your message here..."
                    className="min-h-[160px] rounded-2xl bg-slate-50 border-slate-100 p-4 resize-none"
                    value={formData.message}
                    onChange={(e) =>
                      setFormData({ ...formData, message: e.target.value })
                    }
                    required
                  />
                </div>

                <Button
                  type="submit"
                  className="w-full h-14 bg-blue-600 hover:bg-blue-700 text-lg font-bold gap-3 shadow-xl shadow-blue-200"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      Delivering Message...
                    </>
                  ) : (
                    <>
                      <Send className="h-5 w-5" />
                      Send Message
                    </>
                  )}
                </Button>
              </form>
            </div>
          </div>
        </div>
      </section>

      {/* 3. MAP/LOCATION PLACEHOLDER */}
      <section className="py-24 bg-slate-50 border-t">
        <div className="container mx-auto px-4 text-center">
          <Globe className="h-12 w-12 text-slate-300 mx-auto mb-6" />
          <h2 className="text-2xl font-black text-slate-900 mb-4">
            A Global Community of Learners
          </h2>
          <p className="text-slate-500 font-medium max-w-lg mx-auto">
            Our servers are distributed across the globe to ensure your orbits
            load instantly, no matter where you are.
          </p>
        </div>
      </section>
    </div>
  );
}
