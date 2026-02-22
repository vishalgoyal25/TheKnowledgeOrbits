/**
 * Auth API Calls
 */

import apiClient from "./client";
import {
  RegisterRequest,
  RegisterResponse,
  LoginRequest,
  LoginResponse,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  ChangePasswordRequest,
  User,
} from "@/lib/types";

export const authAPI = {
  // Register
  register: async (data: RegisterRequest): Promise<RegisterResponse> => {
    const response = await apiClient.post("/auth/register/", data);
    return response.data;
  },

  // Verify Email
  verifyEmail: async (token: string): Promise<{ message: string }> => {
    const response = await apiClient.post(`/auth/verify-email/${token}/`);
    return response.data;
  },

  // Resend Verification
  resendVerification: async (email: string): Promise<{ message: string }> => {
    const response = await apiClient.post("/auth/resend-verification/", {
      email,
    });
    return response.data;
  },

  // Login
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await apiClient.post("/auth/login/", data);
    return response.data;
  },

  // Logout
  logout: async (): Promise<{ message: string }> => {
    const response = await apiClient.post("/auth/logout/");
    return response.data;
  },

  // Get Current User
  getCurrentUser: async (): Promise<User> => {
    const response = await apiClient.get("/auth/me/");
    return response.data;
  },

  // Forgot Password
  forgotPassword: async (
    data: ForgotPasswordRequest,
  ): Promise<{ message: string }> => {
    const response = await apiClient.post("/auth/forgot-password/", data);
    return response.data;
  },

  // Reset Password
  resetPassword: async (
    token: string,
    data: ResetPasswordRequest,
  ): Promise<{ message: string }> => {
    const response = await apiClient.post(
      `/auth/reset-password/${token}/`,
      data,
    );
    return response.data;
  },

  // Change Password
  changePassword: async (
    data: ChangePasswordRequest,
  ): Promise<{ message: string }> => {
    const response = await apiClient.post("/auth/change-password/", data);
    return response.data;
  },
};
