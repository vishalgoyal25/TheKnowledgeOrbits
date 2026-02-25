"use client";

import { useState } from "react";
import { authAPI } from "@/lib/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle2, Loader2, Mail } from "lucide-react";
import { AxiosError } from "axios";
import { ApiError } from "@/lib/types";

/**
 * ForgotPasswordForm - Initiates passord recovery.
 * Shows a success state with email illustration after submission.
 */
export default function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [message, setMessage] = useState("");

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
      <div className="text-center space-y-4 py-4">
        <div className="mx-auto bg-green-100 rounded-full p-5 w-fit">
          <CheckCircle2 className="h-10 w-10 text-green-600" />
        </div>
        <h3 className="text-lg font-semibold text-green-800">
          Check your inbox!
        </h3>
        <p className="text-gray-600 text-sm leading-relaxed">{message}</p>
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-left">
          <p className="text-blue-800 text-sm flex items-start gap-2">
            <Mail className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <span>
              We sent a reset link to <strong>{email}</strong>. The link expires
              in 1 hour. Check your spam folder if you don&apos;t see it.
            </span>
          </p>
        </div>
        <Button
          variant="outline"
          className="w-full"
          onClick={() => {
            setStatus("idle");
            setEmail("");
          }}
        >
          Try another email
        </Button>
      </div>
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
        <label className="block text-sm font-medium mb-1.5 text-gray-700">
          Email Address
        </label>
        <Input
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={status === "loading"}
          className="h-11"
        />
      </div>

      <Button
        type="submit"
        className="w-full h-11 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-base font-semibold"
        disabled={status === "loading"}
      >
        {status === "loading" ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Sending link...
          </>
        ) : (
          "Send Reset Link"
        )}
      </Button>
    </form>
  );
}
