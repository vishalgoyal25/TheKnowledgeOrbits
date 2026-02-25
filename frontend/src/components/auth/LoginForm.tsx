"use client";
import { useState } from "react";
import { useAuth } from "@/lib/auth/useAuth";
import { authAPI } from "@/lib/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AxiosError } from "axios";
import { ApiError } from "@/lib/types";
import { CheckCircle2, Mail, Loader2, Eye, EyeOff } from "lucide-react";

/**
 * LoginForm - Full-featured login with:
 * - Email not verified handling (with resend button)
 * - Post-registration and post-verification success banners
 * - Password visibility toggle
 * - Forgot password link
 */
export default function LoginForm() {
  const { login } = useAuth();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect") || undefined;
  const isRegistered = searchParams.get("registered") === "true";
  const isVerified = searchParams.get("verified") === "true";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Email not verified state
  const [showVerificationNeeded, setShowVerificationNeeded] = useState(false);
  const [unverifiedEmail, setUnverifiedEmail] = useState("");
  const [resendStatus, setResendStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [resendMessage, setResendMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setShowVerificationNeeded(false);
    setLoading(true);

    try {
      await login({ email, password }, redirectTo);
    } catch (err) {
      const axiosError = err as AxiosError<ApiError>;
      const errorCode = axiosError.response?.data?.error;

      if (errorCode === "EMAIL_NOT_VERIFIED") {
        setShowVerificationNeeded(true);
        setUnverifiedEmail(
          (axiosError.response?.data?.email as string) || email,
        );
      } else if (errorCode === "INVALID_CREDENTIALS") {
        setError("Invalid email or password. Please try again.");
      } else {
        setError(
          axiosError.response?.data?.message ||
            axiosError.response?.data?.error ||
            "Login failed. Please check your credentials.",
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = async () => {
    setResendStatus("loading");
    try {
      const response = await authAPI.resendVerification(unverifiedEmail);
      setResendStatus("success");
      setResendMessage(
        response.message || "Verification email sent! Check your inbox.",
      );
    } catch (err) {
      const axiosError = err as AxiosError<ApiError>;
      setResendStatus("error");
      setResendMessage(
        axiosError.response?.data?.message ||
          "Failed to send. Please try again.",
      );
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Post-registration banner */}
      {isRegistered && (
        <Alert className="bg-blue-50 border-blue-200">
          <Mail className="h-4 w-4 text-blue-600" />
          <AlertDescription className="text-blue-800">
            <strong>Registration successful!</strong> We&apos;ve sent a
            verification email. Please check your inbox and verify your email
            before signing in.
          </AlertDescription>
        </Alert>
      )}

      {/* Post-verification banner */}
      {isVerified && (
        <Alert className="bg-green-50 border-green-200">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">
            <strong>Email verified!</strong> Your account is now active. Sign in
            to get started.
          </AlertDescription>
        </Alert>
      )}

      {/* Generic error */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Email not verified section */}
      {showVerificationNeeded && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-3">
          <div className="flex items-start gap-3">
            <Mail className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-amber-900 font-medium text-sm">
                Email not verified
              </p>
              <p className="text-amber-700 text-sm mt-1">
                Please verify your email address ({unverifiedEmail}) before
                signing in. Check your inbox for the verification link.
              </p>
            </div>
          </div>

          {resendStatus === "success" ? (
            <Alert className="bg-green-50 border-green-200">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800 text-sm">
                {resendMessage}
              </AlertDescription>
            </Alert>
          ) : (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="w-full border-amber-300 text-amber-800 hover:bg-amber-100"
              onClick={handleResendVerification}
              disabled={resendStatus === "loading"}
            >
              {resendStatus === "loading" ? (
                <>
                  <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                  Sending...
                </>
              ) : (
                "Resend Verification Email"
              )}
            </Button>
          )}

          {resendStatus === "error" && (
            <p className="text-red-600 text-xs text-center">{resendMessage}</p>
          )}
        </div>
      )}

      <div>
        <label className="block text-sm font-medium mb-1.5 text-gray-700">
          Email
        </label>
        <Input
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="h-11"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1.5 text-gray-700">
          Password
        </label>
        <div className="relative">
          <Input
            type={showPassword ? "text" : "password"}
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
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
      </div>

      <div className="text-right">
        <Link
          href="/auth/forgot-password"
          className="text-sm text-blue-600 hover:underline"
        >
          Forgot password?
        </Link>
      </div>

      <Button
        type="submit"
        className="w-full h-11 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-base font-semibold"
        disabled={loading}
      >
        {loading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Signing in...
          </>
        ) : (
          "Sign In"
        )}
      </Button>
    </form>
  );
}
