/**
 * useAuth Hook - Access Auth Context
 */

"use client";

import { useContext } from "react";
import { AuthContext, AuthContextType } from "./AuthContext";

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return context;
}
