"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth/useAuth";
import { tokenManager } from "@/lib/auth/token-manager";
import { Loader2 } from "lucide-react";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  // A user with a stored token HAS a session. Only bounce to /login when there
  // is genuinely no token — never on a transient user-fetch failure (which used
  // to log the user out intermittently). The backend still enforces auth on
  // every API call, so this is safe: an invalid token gets cleared on its 401.
  const hasSession = isAuthenticated || tokenManager.hasTokens();

  useEffect(() => {
    if (!isLoading && !hasSession) {
      // Redirect to login, but save the current path to return after login
      router.push(`/auth/login?redirect=${encodeURIComponent(pathname)}`);
    }
  }, [hasSession, isLoading, router, pathname]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!hasSession) {
    return null;
  }

  return <>{children}</>;
}
