/**
 * Auth Context - Global Authentication State
 */

'use client';

import { createContext } from 'react';
import { User, LoginRequest, RegisterRequest } from '@/lib/types';

export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginRequest, redirectTo?: string) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
