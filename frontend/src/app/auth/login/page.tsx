/**
 * Login Page
 */

"use client";

import { Suspense } from "react";
import LoginForm from "@/components/auth/LoginForm";
import { Loader2 } from "lucide-react";
import Link from "next/link";

export default function LoginPage() {
  return (
    <div className="container relative min-h-[calc(100vh-8rem)] flex-col items-center justify-center grid lg:max-w-none lg:grid-cols-1 lg:px-0">
      <div className="lg:p-8">
        <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[450px]">
          <div className="flex flex-col space-y-2 text-center">
            <h1 className="text-2xl font-semibold tracking-tight">
              Welcome Back
            </h1>
            <p className="text-sm text-muted-foreground">
              Sign in to your TheKnowledgeOrbits account
            </p>
          </div>
          <Suspense
            fallback={
              <div className="flex justify-center p-8">
                <Loader2 className="animate-spin" />
              </div>
            }
          >
            <LoginForm />
          </Suspense>

          <div className="text-center text-sm">
            <span className="text-muted-foreground">
              Don&apos;t have an account?{" "}
            </span>
            <Link
              href="/auth/register"
              className="text-blue-600 hover:underline font-semibold"
            >
              Create one for free
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
