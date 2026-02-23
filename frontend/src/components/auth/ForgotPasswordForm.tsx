"use client";

import { useState } from "react";
import { authAPI } from "@/lib/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle2 } from "lucide-react";

import { AxiosError } from "axios";
import { ApiError } from "@/lib/types";

/**
 * ForgotPasswordForm - Initiates the password recovery workflow.
 * Collects the user's email and triggers the backend reset link generator.
 */
export default function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [message, setMessage] = useState("");

  /**
   * Submits the recovery request.
   * On success, shows a confirmation message.
   * On failure, displays the specific backend error for the user.
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("loading");
    setMessage("");

    try {
      const response = await authAPI.forgotPassword({ email });
      setStatus("success");
      setMessage(response.message || "Password reset link sent to your email.");
    } catch (err) {
      const axiosError = err as AxiosError<ApiError>;
      setStatus("error");
      setMessage(
        axiosError.response?.data?.message ||
          axiosError.response?.data?.error ||
          "Failed to send reset link. Please verify your email.",
      );
    }
  };

  if (status === "success") {
    return (
      <Alert className="bg-green-50 border-green-200">
        <CheckCircle2 className="h-4 w-4 text-green-600" />
        <AlertDescription className="text-green-800">
          {message}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {status === "error" && (
        <Alert variant="destructive">
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      )}

      <div>
        <label className="block text-sm font-medium mb-1">Email Address</label>
        <Input
          type="email"
          placeholder="name@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={status === "loading"}
        />
      </div>

      <Button type="submit" className="w-full" disabled={status === "loading"}>
        {status === "loading" ? "Sending link..." : "Send Reset Link"}
      </Button>
    </form>
  );
}
