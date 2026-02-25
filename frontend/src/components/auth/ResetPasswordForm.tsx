"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authAPI } from "@/lib/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AxiosError } from "axios";
import { ApiError } from "@/lib/types";
import { Eye, EyeOff, Loader2, Check, X, CheckCircle2 } from "lucide-react";

interface ResetPasswordFormProps {
  token: string;
}

/**
 * ResetPasswordForm - Final step in the password recovery flow.
 * Includes password strength indicator and match validation.
 */
export default function ResetPasswordForm({ token }: ResetPasswordFormProps) {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [status, setStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [message, setMessage] = useState("");

  // Password strength
  const checks = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
  };
  const strengthScore = Object.values(checks).filter(Boolean).length;
  const passwordsMatch =
    confirmPassword.length > 0 && password === confirmPassword;
  const passwordsMismatch =
    confirmPassword.length > 0 && password !== confirmPassword;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      setStatus("error");
      setMessage("Passwords do not match");
      return;
    }

    if (strengthScore < 3) {
      setStatus("error");
      setMessage("Please choose a stronger password");
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

      setTimeout(() => {
        router.push("/auth/login");
      }, 3000);
    } catch (err) {
      const axiosError = err as AxiosError<ApiError>;
      setStatus("error");
      setMessage(
        axiosError.response?.data?.message ||
          axiosError.response?.data?.error ||
          "Failed to reset password. The link may be expired or invalid.",
      );
    }
  };

  if (status === "success") {
    return (
      <div className="text-center space-y-4 py-4">
        <div className="mx-auto bg-green-100 rounded-full p-5 w-fit animate-in zoom-in duration-300">
          <CheckCircle2 className="h-10 w-10 text-green-600" />
        </div>
        <h3 className="text-lg font-semibold text-green-800">
          Password Reset!
        </h3>
        <p className="text-gray-600 text-sm">{message}</p>
        <p className="text-sm text-gray-500">
          Redirecting to login in 3 seconds...
        </p>
        <Button className="w-full" onClick={() => router.push("/auth/login")}>
          Go to Login Now
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
          New Password
        </label>
        <div className="relative">
          <Input
            type={showPassword ? "text" : "password"}
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            disabled={status === "loading"}
            className="h-11 pr-10"
          />
          <button
            type="button"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            onClick={() => setShowPassword(!showPassword)}
            tabIndex={-1}
          >
            {showPassword ? (
              <EyeOff className="h-4 w-4" />
            ) : (
              <Eye className="h-4 w-4" />
            )}
          </button>
        </div>

        {/* Password strength */}
        {password.length > 0 && (
          <div className="mt-2 space-y-2">
            <div className="flex gap-1">
              {[1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className={`h-1.5 flex-1 rounded-full transition-colors ${
                    i <= strengthScore
                      ? strengthScore <= 1
                        ? "bg-red-500"
                        : strengthScore <= 2
                          ? "bg-orange-500"
                          : strengthScore <= 3
                            ? "bg-yellow-500"
                            : "bg-green-500"
                      : "bg-gray-200"
                  }`}
                />
              ))}
            </div>
            <div className="grid grid-cols-2 gap-1">
              {[
                { label: "8+ characters", ok: checks.length },
                { label: "Uppercase", ok: checks.uppercase },
                { label: "Lowercase", ok: checks.lowercase },
                { label: "Number", ok: checks.number },
              ].map((check) => (
                <div
                  key={check.label}
                  className={`flex items-center gap-1 text-xs ${
                    check.ok ? "text-green-600" : "text-gray-400"
                  }`}
                >
                  {check.ok ? (
                    <Check className="h-3 w-3" />
                  ) : (
                    <X className="h-3 w-3" />
                  )}
                  {check.label}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium mb-1.5 text-gray-700">
          Confirm New Password
        </label>
        <div className="relative">
          <Input
            type={showConfirm ? "text" : "password"}
            placeholder="••••••••"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            disabled={status === "loading"}
            className={`h-11 pr-10 ${
              passwordsMatch
                ? "border-green-500 focus-visible:ring-green-500"
                : passwordsMismatch
                  ? "border-red-500 focus-visible:ring-red-500"
                  : ""
            }`}
          />
          <button
            type="button"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            onClick={() => setShowConfirm(!showConfirm)}
            tabIndex={-1}
          >
            {showConfirm ? (
              <EyeOff className="h-4 w-4" />
            ) : (
              <Eye className="h-4 w-4" />
            )}
          </button>
        </div>
        {passwordsMatch && (
          <p className="text-xs text-green-600 mt-1 flex items-center gap-1">
            <Check className="h-3 w-3" /> Passwords match
          </p>
        )}
        {passwordsMismatch && (
          <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
            <X className="h-3 w-3" /> Passwords do not match
          </p>
        )}
      </div>

      <Button
        type="submit"
        className="w-full h-11 bg-gradient-to-r from-red-500 to-orange-500 hover:from-red-600 hover:to-orange-600 text-base font-semibold"
        disabled={status === "loading"}
      >
        {status === "loading" ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Resetting...
          </>
        ) : (
          "Reset Password"
        )}
      </Button>
    </form>
  );
}
