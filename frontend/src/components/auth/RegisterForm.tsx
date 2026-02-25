"use client";
import { useState } from "react";
import { useAuth } from "@/lib/auth/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AxiosError } from "axios";
import { ApiError } from "@/lib/types";
import { Eye, EyeOff, Loader2, Check, X } from "lucide-react";

/**
 * RegisterForm - Premium registration with:
 * - Real-time password strength indicator
 * - Password match validation
 * - Show/hide password toggles
 * - Gradient submit button
 */
export default function RegisterForm() {
  const { register } = useAuth();
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    password_confirm: "",
    full_name: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  // Password strength checks
  const password = formData.password;
  const checks = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
  };
  const strengthScore = Object.values(checks).filter(Boolean).length;
  const passwordsMatch =
    formData.password_confirm.length > 0 &&
    formData.password === formData.password_confirm;
  const passwordsMismatch =
    formData.password_confirm.length > 0 &&
    formData.password !== formData.password_confirm;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (formData.password !== formData.password_confirm) {
      setError("Passwords do not match");
      return;
    }

    if (strengthScore < 3) {
      setError("Please choose a stronger password");
      return;
    }

    setLoading(true);
    try {
      await register(formData);
    } catch (err) {
      const axiosError = err as AxiosError<ApiError>;
      const data = axiosError.response?.data;

      // Handle field-level validation errors from DRF
      if (data && typeof data === "object" && !data.message && !data.error) {
        const fieldErrors = Object.entries(data)
          .map(([key, val]) => {
            const msgs = Array.isArray(val) ? val.join(", ") : String(val);
            return `${key}: ${msgs}`;
          })
          .join("\n");
        setError(fieldErrors || "Registration failed.");
      } else {
        setError(
          data?.message ||
            data?.error ||
            "Registration failed. Please try again.",
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <Alert variant="destructive">
          <AlertDescription className="whitespace-pre-line">
            {error}
          </AlertDescription>
        </Alert>
      )}

      <div>
        <label className="block text-sm font-medium mb-1.5 text-gray-700">
          Full Name
        </label>
        <Input
          placeholder="John Doe"
          value={formData.full_name}
          onChange={(e) => handleChange("full_name", e.target.value)}
          className="h-11"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1.5 text-gray-700">
          Email <span className="text-red-500">*</span>
        </label>
        <Input
          type="email"
          placeholder="you@example.com"
          value={formData.email}
          onChange={(e) => handleChange("email", e.target.value)}
          required
          className="h-11"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1.5 text-gray-700">
          Password <span className="text-red-500">*</span>
        </label>
        <div className="relative">
          <Input
            type={showPassword ? "text" : "password"}
            placeholder="••••••••"
            value={formData.password}
            onChange={(e) => handleChange("password", e.target.value)}
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

        {/* Password strength indicator */}
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
          Confirm Password <span className="text-red-500">*</span>
        </label>
        <div className="relative">
          <Input
            type={showConfirm ? "text" : "password"}
            placeholder="••••••••"
            value={formData.password_confirm}
            onChange={(e) => handleChange("password_confirm", e.target.value)}
            required
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
        className="w-full h-11 bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700 text-base font-semibold"
        disabled={loading}
      >
        {loading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Creating account...
          </>
        ) : (
          "Create Account"
        )}
      </Button>

      <p className="text-xs text-gray-500 text-center">
        By creating an account, you agree to our Terms of Service and Privacy
        Policy.
      </p>
    </form>
  );
}
