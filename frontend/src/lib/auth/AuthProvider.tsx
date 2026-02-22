/**
 * Auth Provider - Manages Authentication State
 */

"use client";

import { useState, useEffect, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { AuthContext } from "./AuthContext";
import { authAPI } from "@/lib/api/auth";
import { tokenManager } from "./token-manager";
import { User, LoginRequest, RegisterRequest } from "@/lib/types";

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
    try {
      if (tokenManager.hasTokens()) {
        const userData = await authAPI.getCurrentUser();
        setUser(userData);
      }
    } catch (error) {
      console.error("Failed to load user:", error);
      tokenManager.clearTokens();
    } finally {
      setIsLoading(false);
    }
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
