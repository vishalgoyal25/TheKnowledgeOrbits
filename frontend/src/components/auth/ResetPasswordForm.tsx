"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authAPI } from "@/lib/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";

import { AxiosError } from "axios";
import { ApiError } from "@/lib/types";

/**
 * Props for the ResetPasswordForm component.
 */
interface ResetPasswordFormProps {
  /** The unique reset token extracted from the URL. */
  token: string;
}

/**
 * ResetPasswordForm - Final step in the password recovery flow.
 * Allows users to set a new password using a verified token.
 */
export default function ResetPasswordForm({ token }: ResetPasswordFormProps) {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [status, setStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [message, setMessage] = useState("");

  /**
   * Validates matching passwords and submits the reset request.
   * On success, briefly shows a confirmation before redirecting to login.
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      setStatus("error");
      setMessage("Passwords do not match");
      return;
    }

    setStatus("loading");
    setMessage("");

    try {
      const response = await authAPI.resetPassword(token, {
        password,
        password_confirm: confirmPassword,
      });
      setStatus("success");
      setMessage(response.message || "Password has been reset successfully.");

      // Redirect after a short delay so the user sees the success state
      setTimeout(() => {
        router.push("/auth/login");
      }, 3000);
    } catch (err) {
      const axiosError = err as AxiosError<ApiError>;
      setStatus("error");
      setMessage(axiosError.response?.data?.message || axiosError.response?.data?.error || "Failed to reset password. The link may be expired or invalid.");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {status === "error" && (
        <Alert variant="destructive">
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      )}

      {status === "success" && (
        <Alert className="bg-green-50 border-green-200">
          <AlertDescription className="text-green-800">
            {message} Redirecting to login...
          </AlertDescription>
        </Alert>
      )}

      <div>
        <label className="block text-sm font-medium mb-1">New Password</label>
        <Input
          type="password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          disabled={status === "loading" || status === "success"}
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          Confirm New Password
        </label>
        <Input
          type="password"
          placeholder="••••••••"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          disabled={status === "loading" || status === "success"}
        />
      </div>

      <Button
        type="submit"
        className="w-full"
        disabled={status === "loading" || status === "success"}
      >
        {status === "loading" ? "Resetting..." : "Reset Password"}
      </Button>
    </form>
  );
}
