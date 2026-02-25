/**
 * Email Verification Page
 */

"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { authAPI } from "@/lib/api/auth";
import { Button } from "@/components/ui/button";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { AxiosError } from "axios";
import { ApiError } from "@/lib/types";

export default function VerifyEmailPage() {
  const params = useParams();
  const router = useRouter();
  const token = params.token as string;

  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading",
  );
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("Invalid verification link.");
      return;
    }

    const verify = async () => {
      try {
        const response = await authAPI.verifyEmail(token);
        setStatus("success");
        setMessage(response.message || "Your email has been verified!");
      } catch (err) {
        const axiosError = err as AxiosError<ApiError>;
        setStatus("error");
        setMessage(
          axiosError.response?.data?.message ||
            axiosError.response?.data?.error ||
            "Verification failed. Please try again.",
        );
      }
    };

    verify();
  }, [token]);

  return (
    <div className="container relative min-h-[calc(100vh-8rem)] flex-col items-center justify-center grid lg:max-w-none lg:grid-cols-1 lg:px-0">
      <div className="lg:p-8">
        <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[450px] text-center">
          {status === "loading" && (
            <div className="flex flex-col items-center space-y-4">
              <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
              <h1 className="text-2xl font-semibold">
                Verifying your email...
              </h1>
              <p className="text-muted-foreground">Please wait a moment.</p>
            </div>
          )}

          {status === "success" && (
            <div className="flex flex-col items-center space-y-4">
              <CheckCircle2 className="h-16 w-16 text-green-600" />
              <h1 className="text-2xl font-semibold tracking-tight">
                Verified Successfully!
              </h1>
              <p className="text-muted-foreground">{message}</p>
              <Button
                onClick={() => router.push("/auth/login?verified=true")}
                className="w-full"
              >
                Continue to Login
              </Button>
            </div>
          )}

          {status === "error" && (
            <div className="flex flex-col items-center space-y-4">
              <XCircle className="h-16 w-16 text-red-500" />
              <h1 className="text-2xl font-semibold tracking-tight">
                Verification Failed
              </h1>
              <p className="text-red-600">{message}</p>
              <Button
                variant="outline"
                onClick={() => router.push("/auth/login")}
                className="w-full"
              >
                Back to Login
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
