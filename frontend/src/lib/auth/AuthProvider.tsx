/**
 * Auth Provider - Manages Authentication State
 */

"use client";

import { useState, useEffect, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { AxiosError } from "axios";
import { AuthContext } from "./AuthContext";
import { authAPI } from "@/lib/api/auth";
import { tokenManager } from "./token-manager";
import { User, LoginRequest, RegisterRequest } from "@/lib/types";
import { createLogger } from "@/lib/logger";

const logger = createLogger("Auth");

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const isAuthenticated = !!user;

  // Load user on mount
  useEffect(() => {
    loadUser();
  }, []);

  const loadUser = async () => {
    if (!tokenManager.hasTokens()) {
      setIsLoading(false);
      return;
    }

    // Retry transient failures so a flaky/cold-starting backend (Render free
    // tier spins down on idle) does NOT bounce a logged-in user to /login.
    // Only a genuine 401/403 means the token is invalid → real logout.
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const userData = await authAPI.getCurrentUser();
        setUser(userData);
        setIsLoading(false);
        return;
      } catch (error) {
        const status = (error as AxiosError)?.response?.status;
        if (status === 401 || status === 403) {
          logger.error("Auth token invalid — clearing session:", error);
          tokenManager.clearTokens();
          setIsLoading(false);
          return;
        }
        // Transient (network/timeout/5xx/cold-start) — keep tokens, back off, retry.
        logger.error(`getCurrentUser attempt ${attempt + 1} failed:`, error);
        await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
      }
    }
    // All retries exhausted on transient errors — do NOT clear tokens or log
    // out; the session token is still valid and ProtectedRoute keeps the user
    // in place. A later navigation/refresh re-validates.
    setIsLoading(false);
  };

  const login = async (data: LoginRequest, redirectTo?: string) => {
    const response = await authAPI.login(data);

    // Store tokens
    tokenManager.setTokens(response.tokens.access, response.tokens.refresh);

    // Set user
    setUser(response.user);

    // Redirect to specified path or dashboard
    router.push(redirectTo || "/dashboard");
  };

  const register = async (data: RegisterRequest) => {
    await authAPI.register(data);
    // Don't login - redirect to verify email message
    router.push("/auth/login?registered=true");
  };

  const logout = () => {
    // Call logout API (optional - token invalidation)
    authAPI.logout().catch(() => {});

    // Clear tokens
    tokenManager.clearTokens();

    // Clear user
    setUser(null);

    // Redirect to login
    router.push("/auth/login");
  };

  const refreshUser = async () => {
    if (tokenManager.hasTokens()) {
      const userData = await authAPI.getCurrentUser();
      setUser(userData);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
