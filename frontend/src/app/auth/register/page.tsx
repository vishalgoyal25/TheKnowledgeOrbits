/**
 * Register Page
 */

"use client";

import RegisterForm from "@/components/auth/RegisterForm";
import Link from "next/link";

export default function RegisterPage() {
  return (
    <div className="container relative min-h-[calc(100vh-8rem)] flex-col items-center justify-center grid lg:max-w-none lg:grid-cols-1 lg:px-0">
      <div className="lg:p-8">
        <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[500px]">
          <div className="flex flex-col space-y-2 text-center">
            <h1 className="text-2xl font-semibold tracking-tight">
              Create Account
            </h1>
            <p className="text-sm text-muted-foreground">
              Join TheKnowledgeOrbits and start your UPSC journey
            </p>
          </div>
          <RegisterForm />

          <div className="text-center text-sm mt-6">
            <span className="text-muted-foreground">
              Already have an account?{" "}
            </span>
            <Link
              href="/auth/login"
              className="text-blue-600 hover:underline font-semibold"
            >
              Sign in here
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
