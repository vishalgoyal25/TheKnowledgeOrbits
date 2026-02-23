"use client";

import React, { useState } from "react";
import {
  MessageSquare,
  Send,
  User,
  Mail,
  Phone,
  MapPin,
  School,
  GraduationCap,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { supportAPI, FeedbackData } from "@/lib/api/support";
import { useToast } from "@/hooks/use-toast";
import { AxiosError } from "axios";
import { ApiError } from "@/lib/types";

/**
 * FeedbackButton - A floating action button (FAB) that opens a comprehensive
 * feedback dialog. Supports deep-linking via #feedback hash and provides
 * a multi-field form for user suggestions.
 */
export default function FeedbackButton() {
  const [isOpen, setIsOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { toast } = useToast();

  // Listen for #feedback in URL to open dialog
  React.useEffect(() => {
    const handleHashChange = () => {
      if (window.location.hash === "#feedback") {
        setIsOpen(true);
        // Clear the hash after opening to prevent re-triggers
        window.history.replaceState(
          null,
          "",
          window.location.pathname + window.location.search,
        );
      }
    };

    // Global click interceptor for #feedback links
    const handleGlobalClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const link = target.closest("a");
      // Check if the link href contains #feedback (handles /#feedback, #feedback, etc.)
      const href = link?.getAttribute("href");
      if (href && (href === "#feedback" || href.endsWith("/#feedback"))) {
        e.preventDefault();
        e.stopPropagation();
        setIsOpen(true);
      }
    };

    // Check on mount
    handleHashChange();

    // Listen for changes and clicks
    window.addEventListener("hashchange", handleHashChange);
    window.addEventListener("click", handleGlobalClick);
    return () => {
      window.removeEventListener("hashchange", handleHashChange);
      window.removeEventListener("click", handleGlobalClick);
    };
  }, []);

  const [formData, setFormData] = useState<FeedbackData>({
    name: "",
    email: "",
    phone: "",
    city: "",
    institution: "",
    user_type: "aspirant",
    message: "",
  });

  /**
   * Submits feedback data to the support API.
   * On success: shows toast and resets form.
   * On error: notifies user with specific message if available.
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name || !formData.email || !formData.message) {
      toast({
        title: "Required Fields Missing",
        description: "Please fill in your name, email, and message.",
        variant: "destructive",
      });
      return;
    }

    setIsSubmitting(true);
    try {
      await supportAPI.submitFeedback(formData);
      toast({
        title: "Feedback Received!",
        description:
          "Thank you for helping us orbit better. We'll look into your message.",
      });
      setFormData({
        name: "",
        email: "",
        phone: "",
        city: "",
        institution: "",
        user_type: "aspirant",
        message: "",
      });
      setIsOpen(false);
    } catch (error) {
      const axiosError = error as AxiosError<ApiError>;
      toast({
        title: "Submission Failed",
        description: axiosError.response?.data?.message || axiosError.response?.data?.error || "Something went wrong. Please try again later.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button
          className="fixed bottom-6 right-6 h-14 w-14 rounded-full shadow-2xl bg-blue-600 hover:bg-blue-700 text-white z-50 p-0 flex items-center justify-center group"
          aria-label="Give Feedback"
        >
          <MessageSquare className="h-6 w-6 group-hover:scale-110 transition-transform" />
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-2xl">
            <GraduationCap className="h-6 w-6 text-blue-600" />
            Share Your Feedback
          </DialogTitle>
          <DialogDescription>
            Help us improve TheKnowledgeOrbits. Tell us what you like or what we
            can do better.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name" className="text-sm font-bold">
                Full Name *
              </Label>
              <div className="relative">
                <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  id="name"
                  placeholder="John Doe"
                  className="pl-10"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-bold">
                Email Address *
              </Label>
              <div className="relative">
                <Mail className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  id="email"
                  type="email"
                  placeholder="john@example.com"
                  className="pl-10"
                  value={formData.email}
                  onChange={(e) =>
                    setFormData({ ...formData, email: e.target.value })
                  }
                  required
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="phone" className="text-sm font-bold opacity-70">
                Phone (Optional)
              </Label>
              <div className="relative">
                <Phone className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  id="phone"
                  placeholder="+91..."
                  className="pl-10"
                  value={formData.phone}
                  onChange={(e) =>
                    setFormData({ ...formData, phone: e.target.value })
                  }
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="city" className="text-sm font-bold opacity-70">
                City (Optional)
              </Label>
              <div className="relative">
                <MapPin className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  id="city"
                  placeholder="e.g. New Delhi"
                  className="pl-10"
                  value={formData.city}
                  onChange={(e) =>
                    setFormData({ ...formData, city: e.target.value })
                  }
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="user_type" className="text-sm font-bold">
                I am a...
              </Label>
              <Select
                value={formData.user_type}
                onValueChange={(value: FeedbackData["user_type"]) =>
                  setFormData({ ...formData, user_type: value })
                }
              >
                <SelectTrigger id="user_type">
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="aspirant">UPSC Aspirant</SelectItem>
                  <SelectItem value="student_college">
                    College Student
                  </SelectItem>
                  <SelectItem value="student_school">School Student</SelectItem>
                  <SelectItem value="educator">Educator/Teacher</SelectItem>
                  <SelectItem value="researcher">Researcher</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label
                htmlFor="institution"
                className="text-sm font-bold opacity-70"
              >
                Institution (Optional)
              </Label>
              <div className="relative">
                <School className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  id="institution"
                  placeholder="School/College Name"
                  className="pl-10"
                  value={formData.institution}
                  onChange={(e) =>
                    setFormData({ ...formData, institution: e.target.value })
                  }
                />
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="message" className="text-sm font-bold">
              Your Feedback *
            </Label>
            <Textarea
              id="message"
              placeholder="What's on your mind? We'd love to hear your thoughts..."
              className="min-h-[120px] resize-none"
              value={formData.message}
              onChange={(e) =>
                setFormData({ ...formData, message: e.target.value })
              }
              required
            />
          </div>

          <DialogFooter className="pt-4">
            <Button
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white gap-2 h-12 text-lg font-bold shadow-lg"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Orbiting your feedback...
                </>
              ) : (
                <>
                  <Send className="h-5 w-5" />
                  Submit Feedback
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
