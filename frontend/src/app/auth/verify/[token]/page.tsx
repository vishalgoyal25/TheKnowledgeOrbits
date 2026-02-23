/**
 * Email Verification Page
 */

"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { authAPI } from "@/lib/api/auth";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";

import { AxiosError } from "axios";
import { ApiError } from "@/lib/types";

/**
 * VerifyEmailPage - Automated landing page for email verification links.
 * Extracts the token from the URL and calls the verification API on mount.
 */
export default function VerifyEmailPage() {
  const params = useParams();
  const router = useRouter();
  const token = params.token as string;

  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading",
  );
  const [message, setMessage] = useState("");

  /**
   * Effect hook to trigger verification as soon as the component loads.
   */
  useEffect(() => {
    const verifyEmail = async () => {
      if (!token) return;
      try {
        const response = await authAPI.verifyEmail(token);
        setStatus("success");
        setMessage(response.message);

        // Redirect to login after 3 seconds so user can read the success message
        setTimeout(() => {
          router.push("/auth/login?verified=true");
        }, 3000);
      } catch (error) {
        const axiosError = error as AxiosError<ApiError>;
        setStatus("error");
        setMessage(
          axiosError.response?.data?.message ||
            axiosError.response?.data?.error ||
            "Verification failed. The link may be expired or invalid.",
        );
      }
    };
    verifyEmail();
  }, [token, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-50 to-pink-100 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-center">Email Verification</CardTitle>
        </CardHeader>
        <CardContent>
          {status === "loading" && (
            <div className="flex flex-col items-center gap-4 py-8">
              <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
              <p className="text-gray-600">Verifying your email...</p>
            </div>
          )}

          {status === "success" && (
            <div className="flex flex-col items-center gap-4 py-8">
              <CheckCircle className="h-16 w-16 text-green-600" />
              <Alert className="bg-green-50 border-green-200">
                <AlertDescription className="text-center text-green-800">
                  {message}
                </AlertDescription>
              </Alert>
              <p className="text-sm text-gray-600">Redirecting to login...</p>
            </div>
          )}

          {status === "error" && (
            <div className="flex flex-col items-center gap-4 py-8">
              <XCircle className="h-16 w-16 text-red-600" />
              <Alert className="bg-red-50 border-red-200">
                <AlertDescription className="text-center text-red-800">
                  {message}
                </AlertDescription>
              </Alert>
              <Button
                onClick={() => router.push("/auth/login")}
                variant="outline"
              >
                Back to Login
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
