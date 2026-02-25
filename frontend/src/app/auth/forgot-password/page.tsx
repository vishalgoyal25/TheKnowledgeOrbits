/**
 * Forgot Password Page
 */

"use client";

import ForgotPasswordForm from "@/components/auth/ForgotPasswordForm";
import Link from "next/link";

export default function ForgotPasswordPage() {
  return (
    <div className="container relative min-h-[calc(100vh-8rem)] flex-col items-center justify-center grid lg:max-w-none lg:grid-cols-1 lg:px-0">
      <div className="lg:p-8">
        <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[450px]">
          <div className="flex flex-col space-y-2 text-center">
            <h1 className="text-2xl font-semibold tracking-tight">
              Forgot Password?
            </h1>
            <p className="text-sm text-muted-foreground">
              Enter your email to receive a password reset link
            </p>
          </div>
          <ForgotPasswordForm />

          <div className="text-center text-sm mt-6">
            <Link
              href="/auth/login"
              className="text-blue-600 hover:underline font-semibold"
            >
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
